"""
AI回复引擎V2 - 基于XianyuAutoAgent优化
集成更智能的意图识别、上下文理解和回复生成
"""

import os
import json
import time
import sqlite3
import requests
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from loguru import logger
from openai import OpenAI
from db_manager import db_manager
import re
from datetime import datetime, timedelta


class SmartAIReplyEngine:
    """智能AI回复引擎"""
    
    def __init__(self):
        self.clients = {}
        self.agents = {}
        self._init_prompts()
        self._init_intent_patterns()
        self._init_reply_templates()
    
    def _init_prompts(self):
        """初始化提示词系统"""
        self.prompts = {
            # 意图识别提示词
            'intent_classifier': """你是专业的电商客服意图识别专家。请分析用户消息，返回最匹配的意图类型。

意图类型说明：
- greeting: 打招呼、问好
- inquiry: 商品咨询、功能询问
- price_bargain: 讨价还价、要求优惠
- shipping: 物流相关询问
- after_sales: 售后服务、退换货
- payment: 支付相关问题
- availability: 库存、现货询问
- specification: 规格、参数询问
- comparison: 商品对比
- complaint: 投诉、不满
- spam: 无意义消息、广告
- other: 其他类型

用户消息：{message}

请只返回意图类型，不要解释。""",

            # 智能回复生成提示词
            'smart_reply': """你是专业的电商客服，具备以下特点：
1. 热情友好，用词亲切自然
2. 专业可靠，对商品了如指掌
3. 回复简洁，每句话不超过15字
4. 根据用户意图提供针对性回复

商品信息：
标题：{title}
价格：{price}元
描述：{description}
库存：{stock}
规格：{specs}

对话历史：
{conversation_history}

用户意图：{intent}
用户消息：{message}

回复要求：
- 根据意图类型给出专业回复
- 语言亲切自然，符合电商客服风格
- 总字数控制在50字以内
- 如果是议价，可适当让利但要有底线

请生成回复：""",

            # 回复质量评估
            'reply_quality': """评估以下客服回复的质量，从1-10打分：

商品：{title}
用户问题：{message}
客服回复：{reply}

评估维度：
1. 相关性（是否回答了用户问题）
2. 专业性（是否体现商品知识）
3. 友好性（语言是否亲切）
4. 实用性（是否提供有用信息）

只返回分数（1-10）："""
        }
    
    def _init_intent_patterns(self):
        """初始化意图识别模式"""
        self.intent_patterns = {
            'greeting': [
                r'你好|您好|hi|hello|在吗|在不在',
                r'早上好|下午好|晚上好',
            ],
            'price_bargain': [
                r'便宜|优惠|打折|降价|减价',
                r'最低|底价|能不能|可以.*少|再少',
                r'包邮|免邮|运费',
                r'\d+.*块|元.*行不行|能.*\d+',
            ],
            'inquiry': [
                r'怎么样|如何|效果|质量',
                r'介绍|详细|说说|讲讲',
                r'功能|作用|用途',
            ],
            'shipping': [
                r'发货|快递|物流|邮寄',
                r'几天到|多久|什么时候',
                r'包装|运费',
            ],
            'availability': [
                r'有货|现货|库存|还有',
                r'能买|可以买|有没有',
            ],
            'specification': [
                r'尺寸|大小|规格|参数',
                r'颜色|款式|型号',
                r'重量|材质|配置',
            ]
        }
    
    def _init_reply_templates(self):
        """初始化回复模板"""
        self.reply_templates = {
            'greeting': [
                "亲，您好！有什么可以帮您的吗？",
                "欢迎光临！请问需要了解什么呢？",
                "您好！很高兴为您服务~"
            ],
            'price_bargain': [
                "亲，这个价格已经很优惠了哦！",
                "价格都是实价，质量有保证的！",
                "这个价位性价比很高，值得入手！"
            ],
            'inquiry': [
                "这款商品质量很好，很多客户都满意！",
                "商品详情页有详细介绍，可以看看哦！",
                "有什么具体想了解的可以问我！"
            ],
            'shipping': [
                "我们发货很快，一般当天就能发出！",
                "包邮的哦，用心包装不会损坏！",
                "快递很快，2-3天就能到！"
            ],
            'availability': [
                "有现货的，可以直接拍！",
                "库存充足，放心购买！",
                "现在下单马上就能发货！"
            ],
            'specification': [
                "详细规格可以看商品详情页！",
                "有什么具体参数想了解的？",
                "规格信息都在描述里，很详细！"
            ]
        }
    
    def detect_intent_hybrid(self, message: str, cookie_id: str) -> Tuple[str, float]:
        """混合意图识别：规则+AI"""
        # 1. 先用规则匹配
        rule_intent = self._detect_intent_by_rules(message)
        if rule_intent != 'other':
            return rule_intent, 0.9
        
        # 2. 使用AI识别
        ai_intent = self._detect_intent_by_ai(message, cookie_id)
        return ai_intent, 0.7
    
    def _detect_intent_by_rules(self, message: str) -> str:
        """基于规则的意图识别"""
        message_lower = message.lower()
        
        for intent, patterns in self.intent_patterns.items():
            for pattern in patterns:
                if re.search(pattern, message_lower):
                    return intent
        
        return 'other'
    
    def _detect_intent_by_ai(self, message: str, cookie_id: str) -> str:
        """基于AI的意图识别"""
        try:
            settings = db_manager.get_ai_reply_settings(cookie_id)
            if not settings['ai_enabled'] or not settings['api_key']:
                return 'other'
            
            prompt = self.prompts['intent_classifier'].format(message=message)
            messages = [{"role": "user", "content": prompt}]
            
            if self._is_dashscope_api(settings):
                response = self._call_dashscope_api(settings, messages, max_tokens=20, temperature=0.1)
            else:
                client = self.get_client(cookie_id)
                if not client:
                    return 'other'
                response = self._call_openai_api(client, settings, messages, max_tokens=20, temperature=0.1)
            
            # 提取意图
            intent = response.strip().lower()
            valid_intents = ['greeting', 'inquiry', 'price_bargain', 'shipping', 
                           'after_sales', 'payment', 'availability', 'specification', 
                           'comparison', 'complaint', 'spam', 'other']
            
            return intent if intent in valid_intents else 'other'
            
        except Exception as e:
            logger.error(f"AI意图识别失败: {e}")
            return 'other'
    
    def should_auto_reply(self, message: str, chat_info: dict, cookie_id: str) -> bool:
        """智能判断是否需要自动回复"""
        # 1. 检查是否启用自动回复
        settings = db_manager.get_ai_reply_settings(cookie_id)
        if not settings.get('auto_reply_enabled', True):
            return False
        
        # 2. 检查消息时间（避免回复过期消息）
        message_time = chat_info.get('timestamp', 0)
        if time.time() - message_time > 300:  # 5分钟内的消息才回复
            return False
        
        # 3. 检查是否为垃圾消息
        intent, confidence = self.detect_intent_hybrid(message, cookie_id)
        if intent == 'spam' and confidence > 0.8:
            return False
        
        # 4. 检查回复频率限制
        if self._is_reply_too_frequent(chat_info.get('chat_id'), cookie_id):
            return False
        
        # 5. 检查是否为重复消息
        if self._is_duplicate_message(message, chat_info.get('chat_id'), cookie_id):
            return False
        
        return True
    
    def _is_reply_too_frequent(self, chat_id: str, cookie_id: str) -> bool:
        """检查回复是否过于频繁"""
        try:
            with db_manager.lock:
                cursor = db_manager.conn.cursor()
                # 检查最近5分钟内的回复次数
                five_minutes_ago = datetime.now() - timedelta(minutes=5)
                cursor.execute('''
                SELECT COUNT(*) FROM ai_conversations 
                WHERE chat_id = ? AND cookie_id = ? AND role = 'assistant' 
                AND created_at > ?
                ''', (chat_id, cookie_id, five_minutes_ago.isoformat()))
                
                count = cursor.fetchone()[0]
                return count >= 3  # 5分钟内最多回复3次
        except Exception as e:
            logger.error(f"检查回复频率失败: {e}")
            return False
    
    def _is_duplicate_message(self, message: str, chat_id: str, cookie_id: str) -> bool:
        """检查是否为重复消息"""
        try:
            with db_manager.lock:
                cursor = db_manager.conn.cursor()
                # 检查最近10条消息中是否有相同内容
                cursor.execute('''
                SELECT content FROM ai_conversations 
                WHERE chat_id = ? AND cookie_id = ? AND role = 'user'
                ORDER BY created_at DESC LIMIT 10
                ''', (chat_id, cookie_id))
                
                recent_messages = [row[0] for row in cursor.fetchall()]
                return message in recent_messages
        except Exception as e:
            logger.error(f"检查重复消息失败: {e}")
            return False
    
    def generate_smart_reply(self, message: str, item_info: dict, chat_info: dict, 
                           cookie_id: str) -> Optional[str]:
        """生成智能回复"""
        try:
            # 1. 检查是否需要自动回复
            if not self.should_auto_reply(message, chat_info, cookie_id):
                logger.info(f"跳过自动回复: {chat_info.get('chat_id')}")
                return None
            
            # 2. 意图识别
            intent, confidence = self.detect_intent_hybrid(message, cookie_id)
            logger.info(f"识别意图: {intent} (置信度: {confidence})")
            
            # 3. 获取对话历史
            chat_id = chat_info.get('chat_id')
            context = self.get_conversation_context(chat_id, cookie_id, limit=10)
            
            # 4. 构建对话历史字符串
            history_str = ""
            for msg in context[-5:]:  # 最近5条
                role_name = "用户" if msg['role'] == 'user' else "客服"
                history_str += f"{role_name}: {msg['content']}\n"
            
            # 5. 生成回复
            settings = db_manager.get_ai_reply_settings(cookie_id)
            
            # 如果置信度较低，使用模板回复
            if confidence < 0.6:
                reply = self._get_template_reply(intent, item_info)
            else:
                # 使用AI生成个性化回复
                reply = self._generate_ai_reply(
                    message, item_info, history_str, intent, settings, cookie_id
                )
            
            # 6. 回复质量检查
            if not self._is_reply_quality_good(message, reply, item_info, cookie_id):
                # 质量不好，使用模板回复
                reply = self._get_template_reply(intent, item_info)
            
            # 7. 保存对话记录
            user_id = chat_info.get('user_id', '')
            item_id = chat_info.get('item_id', '')
            
            self.save_conversation(chat_id, cookie_id, user_id, item_id, "user", message, intent)
            self.save_conversation(chat_id, cookie_id, user_id, item_id, "assistant", reply, intent)
            
            logger.info(f"生成智能回复成功: {reply}")
            return reply
            
        except Exception as e:
            logger.error(f"生成智能回复失败: {e}")
            return None
    
    def _generate_ai_reply(self, message: str, item_info: dict, history: str, 
                          intent: str, settings: dict, cookie_id: str) -> str:
        """使用AI生成个性化回复"""
        prompt = self.prompts['smart_reply'].format(
            title=item_info.get('title', '商品'),
            price=item_info.get('price', '面议'),
            description=item_info.get('desc', '暂无描述')[:100],
            stock=item_info.get('stock', '有货'),
            specs=item_info.get('specs', '详见描述'),
            conversation_history=history,
            intent=intent,
            message=message
        )
        
        messages = [{"role": "user", "content": prompt}]
        
        if self._is_dashscope_api(settings):
            return self._call_dashscope_api(settings, messages, max_tokens=100, temperature=0.7)
        else:
            client = self.get_client(cookie_id)
            if not client:
                return self._get_template_reply(intent, item_info)
            return self._call_openai_api(client, settings, messages, max_tokens=100, temperature=0.7)
    
    def _get_template_reply(self, intent: str, item_info: dict) -> str:
        """获取模板回复"""
        templates = self.reply_templates.get(intent, self.reply_templates['inquiry'])
        
        # 简单的模板选择逻辑
        import random
        base_reply = random.choice(templates)
        
        # 根据商品信息个性化
        title = item_info.get('title', '')
        if title and len(title) > 0:
            # 提取商品关键词
            keywords = self._extract_keywords(title)
            if keywords:
                base_reply = f"这款{keywords[0]}{base_reply[2:]}"  # 替换"这款"
        
        return base_reply
    
    def _extract_keywords(self, title: str) -> List[str]:
        """从商品标题提取关键词"""
        # 简单的关键词提取
        common_words = ['手机', '电脑', '衣服', '鞋子', '包包', '化妆品', '食品', '书籍']
        keywords = []
        for word in common_words:
            if word in title:
                keywords.append(word)
        return keywords
    
    def _is_reply_quality_good(self, message: str, reply: str, item_info: dict, 
                              cookie_id: str) -> bool:
        """检查回复质量"""
        try:
            # 基本质量检查
            if not reply or len(reply.strip()) < 5:
                return False
            
            if len(reply) > 200:  # 回复太长
                return False
            
            # 检查是否包含敏感词
            sensitive_words = ['傻', '笨', '滚', '死', '骗子']
            if any(word in reply for word in sensitive_words):
                return False
            
            # 使用AI评估质量（可选）
            settings = db_manager.get_ai_reply_settings(cookie_id)
            if settings.get('quality_check_enabled', False):
                return self._ai_quality_check(message, reply, item_info, cookie_id)
            
            return True
            
        except Exception as e:
            logger.error(f"质量检查失败: {e}")
            return True  # 默认通过
    
    def _ai_quality_check(self, message: str, reply: str, item_info: dict, 
                         cookie_id: str) -> bool:
        """AI质量检查"""
        try:
            settings = db_manager.get_ai_reply_settings(cookie_id)
            prompt = self.prompts['reply_quality'].format(
                title=item_info.get('title', '商品'),
                message=message,
                reply=reply
            )
            
            messages = [{"role": "user", "content": prompt}]
            
            if self._is_dashscope_api(settings):
                response = self._call_dashscope_api(settings, messages, max_tokens=10, temperature=0.1)
            else:
                client = self.get_client(cookie_id)
                if not client:
                    return True
                response = self._call_openai_api(client, settings, messages, max_tokens=10, temperature=0.1)
            
            # 提取分数
            score = re.search(r'\d+', response)
            if score:
                return int(score.group()) >= 7  # 7分以上认为质量好
            
            return True
            
        except Exception as e:
            logger.error(f"AI质量检查失败: {e}")
            return True
    
    # 复用原有的方法
    def get_client(self, cookie_id: str) -> Optional[OpenAI]:
        """获取指定账号的OpenAI客户端"""
        if cookie_id not in self.clients:
            settings = db_manager.get_ai_reply_settings(cookie_id)
            if not settings['ai_enabled'] or not settings['api_key']:
                return None
            
            try:
                self.clients[cookie_id] = OpenAI(
                    api_key=settings['api_key'],
                    base_url=settings['base_url']
                )
                logger.info(f"为账号 {cookie_id} 创建OpenAI客户端成功")
            except Exception as e:
                logger.error(f"创建OpenAI客户端失败 {cookie_id}: {e}")
                return None
        
        return self.clients[cookie_id]
    
    def _is_dashscope_api(self, settings: dict) -> bool:
        """判断是否为DashScope API"""
        model_name = settings.get('model_name', '')
        base_url = settings.get('base_url', '')
        is_custom_model = model_name.lower() in ['custom', '自定义', 'dashscope', 'qwen-custom']
        is_dashscope_url = 'dashscope.aliyuncs.com' in base_url
        return is_custom_model and is_dashscope_url
    
    def _call_dashscope_api(self, settings: dict, messages: list, max_tokens: int = 100, temperature: float = 0.7) -> str:
        """调用DashScope API"""
        base_url = settings['base_url']
        if '/apps/' in base_url:
            app_id = base_url.split('/apps/')[-1].split('/')[0]
        else:
            raise ValueError("DashScope API URL中未找到app_id")
        
        url = f"https://dashscope.aliyuncs.com/api/v1/apps/{app_id}/completion"
        
        system_content = ""
        user_content = ""
        
        for msg in messages:
            if msg['role'] == 'system':
                system_content = msg['content']
            elif msg['role'] == 'user':
                user_content = msg['content']
        
        if system_content and user_content:
            prompt = f"{system_content}\n\n用户问题：{user_content}\n\n请直接回答："
        elif user_content:
            prompt = user_content
        else:
            prompt = "\n".join([f"{msg['role']}: {msg['content']}" for msg in messages])
        
        data = {
            "input": {"prompt": prompt},
            "parameters": {
                "max_tokens": max_tokens,
                "temperature": temperature
            }
        }
        
        headers = {
            "Authorization": f"Bearer {settings['api_key']}",
            "Content-Type": "application/json"
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=30)
        
        if response.status_code != 200:
            raise Exception(f"DashScope API请求失败: {response.status_code} - {response.text}")
        
        result = response.json()
        if 'output' in result and 'text' in result['output']:
            return result['output']['text'].strip()
        else:
            raise Exception(f"DashScope API响应格式错误: {result}")
    
    def _call_openai_api(self, client: OpenAI, settings: dict, messages: list, max_tokens: int = 100, temperature: float = 0.7) -> str:
        """调用OpenAI兼容API"""
        response = client.chat.completions.create(
            model=settings['model_name'],
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature
        )
        return response.choices[0].message.content.strip()
    
    def get_conversation_context(self, chat_id: str, cookie_id: str, limit: int = 20) -> List[Dict]:
        """获取对话上下文"""
        try:
            with db_manager.lock:
                cursor = db_manager.conn.cursor()
                cursor.execute('''
                SELECT role, content FROM ai_conversations 
                WHERE chat_id = ? AND cookie_id = ? 
                ORDER BY created_at DESC LIMIT ?
                ''', (chat_id, cookie_id, limit))
                
                results = cursor.fetchall()
                context = [{"role": row[0], "content": row[1]} for row in reversed(results)]
                return context
        except Exception as e:
            logger.error(f"获取对话上下文失败: {e}")
            return []
    
    def save_conversation(self, chat_id: str, cookie_id: str, user_id: str, 
                         item_id: str, role: str, content: str, intent: str = None):
        """保存对话记录"""
        try:
            with db_manager.lock:
                cursor = db_manager.conn.cursor()
                cursor.execute('''
                INSERT INTO ai_conversations 
                (cookie_id, chat_id, user_id, item_id, role, content, intent)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (cookie_id, chat_id, user_id, item_id, role, content, intent))
                db_manager.conn.commit()
        except Exception as e:
            logger.error(f"保存对话记录失败: {e}")


# 全局智能AI回复引擎实例
smart_ai_reply_engine = SmartAIReplyEngine()