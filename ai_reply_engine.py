"""
AI回复引擎模块
集成XianyuAutoAgent的AI回复功能到现有项目中
"""

import os
import json
import time
import sqlite3
import requests
from typing import List, Dict, Optional
from pathlib import Path
from loguru import logger
from openai import OpenAI
from db_manager import db_manager


class AIReplyEngine:
    """AI回复引擎"""
    
    def __init__(self):
        self.clients = {}  # 存储不同账号的OpenAI客户端
        self.agents = {}   # 存储不同账号的Agent实例
        self.reply_cache = {}  # 回复缓存，避免重复回复
        self.user_emotions = {}  # 用户情感状态缓存
        self._init_default_prompts()
    
    def _init_default_prompts(self):
        """初始化默认提示词"""
        self.prompts = {}
        prompts_dir = Path('prompts')
        
        # 定义提示词文件映射
        prompt_files = {
            'classify': 'classify_prompt.txt',
            'price': 'price_prompt.txt', 
            'tech': 'tech_prompt.txt',
            'default': 'default_prompt.txt',
            'store': 'store_prompt.txt'
        }
        
        # 加载提示词文件
        for key, filename in prompt_files.items():
            file_path = prompts_dir / filename
            if file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        self.prompts[key] = f.read().strip()
                    logger.info(f"成功加载提示词文件: {filename}")
                except Exception as e:
                    logger.error(f"加载提示词文件失败 {filename}: {e}")
                    self.prompts[key] = self._get_default_prompt(key)
            else:
                logger.warning(f"提示词文件不存在: {filename}，使用默认提示词")
                self.prompts[key] = self._get_default_prompt(key)
        
        logger.info(f"提示词初始化完成，加载了 {len(self.prompts)} 个提示词")
    
    def _get_default_prompt(self, prompt_type: str) -> str:
        """获取默认提示词"""
        defaults = {
            'classify': "请分析用户消息的意图，返回：price（价格询问）、tech（使用方法）、store（门店查询）、default（其他）",
            'price': "用户询问价格，请回复：券码价格¥25.8，固定不议价",
            'tech': "用户询问使用方法，请回复：①拍下秒发券码 ②详情页第2、3张图有使用说明",
            'store': "用户询问门店，请回复：请查看详情页门店列表确认是否可用",
            'default': "感谢咨询，有任何问题随时联系我们"
        }
        return defaults.get(prompt_type, "抱歉，暂时无法处理您的问题")
    
    def get_client(self, cookie_id: str) -> Optional[OpenAI]:
        """获取或创建OpenAI客户端"""
        if cookie_id in self.clients:
            return self.clients[cookie_id]
        
        try:
            settings = db_manager.get_ai_reply_settings(cookie_id)
            if not settings['ai_enabled'] or not settings['api_key']:
                return None
            
            # 判断API类型
            is_dashscope = self._is_dashscope_api(settings)
            
            if is_dashscope:
                # 使用DashScope API
                base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
                logger.info(f"创建DashScope客户端 {cookie_id}: base_url={base_url}")
            else:
                # 使用OpenAI兼容API
                base_url = settings.get('base_url', 'https://api.openai.com/v1')
                logger.info(f"创建OpenAI客户端 {cookie_id}: base_url={base_url} api_key=***{settings['api_key'][-4:]}")
            
            client = OpenAI(
                api_key=settings['api_key'],
                base_url=base_url
            )
            
            self.clients[cookie_id] = client
            logger.info(f"为账号 {cookie_id} 创建OpenAI客户端成功，实际base_url: {client.base_url}")
            return client
            
        except Exception as e:
            logger.error(f"创建OpenAI客户端失败 {cookie_id}: {e}")
            return None
    
    def _is_dashscope_api(self, settings: dict) -> bool:
        """判断是否为DashScope API"""
        try:
            model_name = settings.get('model_name', '').lower()
            base_url = settings.get('base_url', '').lower()
            
            # 检查是否为阿里云模型
            dashscope_models = [
                'qwen', 'baichuan', 'chatglm', 'llama2', 'llama3',
                'yi', 'internlm', 'deepseek', 'mixtral'
            ]
            
            is_custom_model = any(model in model_name for model in dashscope_models)
            is_dashscope_url = 'dashscope' in base_url or 'aliyun' in base_url
            
            logger.info(f"API类型判断: model_name={settings.get('model_name')} is_custom_model={is_custom_model} is_dashscope_url={is_dashscope_url}")
            
            return is_custom_model or is_dashscope_url
            
        except Exception as e:
            logger.error(f"判断API类型失败: {e}")
            return False
    
    def clear_client_cache(self, cookie_id: str):
        """清理指定账号的客户端缓存"""
        if cookie_id in self.clients:
            del self.clients[cookie_id]
            logger.info(f"已清理账号 {cookie_id} 的客户端缓存")
    
    def is_ai_enabled(self, cookie_id: str) -> bool:
        """检查指定账号是否启用AI回复"""
        try:
            settings = db_manager.get_ai_reply_settings(cookie_id)
            return settings['ai_enabled']
        except Exception as e:
            logger.error(f"检查AI回复状态失败 {cookie_id}: {e}")
            return False
    
    def _is_invalid_message(self, message: str) -> bool:
        """检查是否为无效消息"""
        if not message or len(message.strip()) == 0:
            return True
        
        # 过滤系统消息和无意义内容
        invalid_patterns = [
            '[去支付]', '[立即购买]', '[确认收货]', '[申请退款]',
            '系统消息', '订单状态', '物流信息', '支付成功',
            '自动回复', '机器人', 'bot'
        ]
        
        message_lower = message.lower().strip()
        for pattern in invalid_patterns:
            if pattern.lower() in message_lower:
                return True
        
        return False
    
    def _rule_based_intent_detection(self, message: str) -> str:
        """基于规则的意图检测"""
        message_lower = message.lower().strip()
        
        # 价格相关关键词
        price_keywords = ['多少钱', '价格', '多少', '费用', '收费', '钱', '元', '块', '价位']
        if any(keyword in message_lower for keyword in price_keywords):
            return 'price'
        
        # 技术/使用相关关键词  
        tech_keywords = ['怎么用', '如何使用', '使用方法', '怎么使用', '操作', '步骤', '流程', '教程']
        if any(keyword in message_lower for keyword in tech_keywords):
            return 'tech'
        
        # 门店相关关键词
        store_keywords = ['门店', '店铺', '地址', '位置', '哪里', '在哪', '能用吗', '可以用吗', '支持']
        if any(keyword in message_lower for keyword in store_keywords):
            return 'store'
        
        return 'default'
    
    def detect_intent(self, message: str, cookie_id: str) -> str:
        """检测用户意图"""
        try:
            # 首先使用规则检测
            rule_intent = self._rule_based_intent_detection(message)
            if rule_intent != 'default':
                logger.info(f"规则匹配意图: {rule_intent}")
                return rule_intent
            
            # 如果规则检测不出来，使用AI检测
            client = self.get_client(cookie_id)
            if not client:
                return 'default'
            
            classify_prompt = self.prompts.get('classify', '')
            if not classify_prompt:
                return 'default'
            
            response = client.chat.completions.create(
                model=db_manager.get_ai_reply_settings(cookie_id).get('model_name', 'gpt-3.5-turbo'),
                messages=[
                    {"role": "system", "content": classify_prompt},
                    {"role": "user", "content": message}
                ],
                max_tokens=50,
                temperature=0.1
            )
            
            intent = response.choices[0].message.content.strip().lower()
            
            # 验证返回的意图是否有效
            valid_intents = ['price', 'tech', 'store', 'default']
            if intent in valid_intents:
                logger.info(f"AI检测意图: {intent}")
                return intent
            else:
                logger.warning(f"AI返回无效意图: {intent}，使用默认")
                return 'default'
                
        except Exception as e:
            logger.error(f"意图检测失败: {e}")
            return 'default'
    
    def _analyze_emotion(self, message: str, history: List[str]) -> str:
        """分析用户情感"""
        try:
            message_lower = message.lower()
            
            # 积极情感
            positive_words = ['谢谢', '好的', '可以', '要了', '买了', '满意', '不错', '好']
            if any(word in message_lower for word in positive_words):
                return 'positive'
            
            # 消极情感
            negative_words = ['不行', '不好', '差', '退款', '投诉', '问题', '错误', '失败']
            if any(word in message_lower for word in negative_words):
                return 'negative'
            
            # 紧急情感
            urgent_words = ['急', '马上', '立即', '快', '赶紧', '尽快']
            if any(word in message_lower for word in urgent_words):
                return 'urgent'
            
            # 犹豫情感
            hesitant_words = ['考虑', '想想', '再说', '看看', '犹豫', '不确定']
            if any(word in message_lower for word in hesitant_words):
                return 'hesitant'
            
            return 'neutral'
            
        except Exception as e:
            logger.error(f"情感分析失败: {e}")
            return 'neutral'
    
    def _handle_voucher_special_cases(self, message: str, item_info: dict, intent: str, 
                                    history: List[str], user_id: str, context: dict) -> Optional[str]:
        """处理餐饮券特殊场景"""
        try:
            message_lower = message.lower().strip()
            
            # 价格询问 - 固定回复
            if intent == 'price' or any(word in message_lower for word in ['多少钱', '价格', '多少']):
                price = item_info.get('price', 25.8)
                return f"券码价格¥{price}，固定不议价"
            
            # 使用方法询问
            if intent == 'tech' or any(word in message_lower for word in ['怎么用', '如何使用', '使用方法']):
                return "①拍下秒发券码 ②详情页第2、3张图有使用说明"
            
            # 门店查询
            if intent == 'store' or any(word in message_lower for word in ['门店', '地址', '能用吗']):
                return "请查看详情页门店列表确认是否可用"
            
            # 退款相关
            if any(word in message_lower for word in ['退款', '退货', '不要了']):
                return "未使用可申请退款，已使用无法退款"
            
            # 系统消息过滤
            if message_lower in ['[去支付]', '[立即购买]', '[确认收货]']:
                return None  # 继续正常流程，不特殊处理
            
            return None  # 没有特殊情况，继续正常处理
            
        except Exception as e:
            logger.error(f"处理餐饮券特殊场景失败: {e}")
            return None
    
    def generate_reply(self, message: str, item_info: dict, chat_id: str,
                      cookie_id: str, user_id: str, item_id: str) -> Optional[str]:
        """生成AI回复"""
        try:
            # 1. 检查是否启用AI回复
            settings = db_manager.get_ai_reply_settings(cookie_id)
            if not settings['ai_enabled'] or not settings['api_key']:
                logger.debug(f"账号 {cookie_id} AI回复未启用或未配置API密钥")
                return None
            
            # 2. 过滤无效消息
            if self._is_invalid_message(message):
                logger.debug(f"过滤无效消息: {message}")
                return None
            
            # 3. 检测用户意图
            intent = self.detect_intent(message, cookie_id)
            logger.info(f"检测到意图: {intent} (账号: {cookie_id})")
            
            # 4. 获取对话历史（简化版本）
            history = []  # 可以后续扩展
            
            # 5. 分析用户情感
            emotion = self._analyze_emotion(message, history)
            
            # 6. 处理餐饮券特殊场景
            special_reply = self._handle_voucher_special_cases(
                message, item_info, intent, history, user_id, {}
            )
            if special_reply:
                return special_reply
            
            # 7. 检查重复回复缓存
            cache_key = f"{chat_id}_{user_id}_{hash(message)}"
            if cache_key in self.reply_cache:
                cached_time = self.reply_cache[cache_key]['time']
                if time.time() - cached_time < 300:  # 5分钟内不重复回复
                    logger.debug(f"跳过重复回复: {message}")
                    return None
            
            # 8. 根据意图选择提示词
            if intent == 'price':
                # 价格询问直接返回固定回复
                reply = f"券码价格¥{item_info.get('price', 25.8)}，固定不议价"
            elif intent in ['tech', 'store', 'default']:
                # 使用AI生成回复
                reply = self._generate_ai_reply(message, item_info, intent, settings, cookie_id)
            else:
                reply = "感谢咨询，有任何问题随时联系我们"
            
            # 9. 缓存回复
            if reply:
                self.reply_cache[cache_key] = {
                    'reply': reply,
                    'time': time.time()
                }
            
            return reply
            
        except Exception as e:
            logger.error(f"AI回复生成失败 {cookie_id}: {e}")
            return None
    
    def _generate_ai_reply(self, message: str, item_info: dict, intent: str, 
                          settings: dict, cookie_id: str) -> Optional[str]:
        """使用AI生成回复"""
        try:
            client = self.get_client(cookie_id)
            if not client:
                return None
            
            # 选择对应的提示词
            prompt_key = intent if intent in self.prompts else 'default'
            system_prompt = self.prompts[prompt_key]
            
            # 构建上下文信息
            context = f"""
商品信息：
- 标题：{item_info.get('title', '未知商品')}
- 价格：¥{item_info.get('price', 0)}
- 描述：{item_info.get('desc', '暂无描述')}

用户消息：{message}
"""
            
            # 判断API类型并调用
            if self._is_dashscope_api(settings):
                logger.info("使用DashScope API生成回复")
                response = client.chat.completions.create(
                    model=settings.get('model_name', 'qwen-turbo'),
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": context}
                    ],
                    max_tokens=200,
                    temperature=0.7
                )
            else:
                logger.info("使用OpenAI兼容API生成回复")
                response = client.chat.completions.create(
                    model=settings.get('model_name', 'gpt-3.5-turbo'),
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": context}
                    ],
                    max_tokens=200,
                    temperature=0.7
                )
            
            reply = response.choices[0].message.content.strip()
            
            if reply:
                logger.info(f"AI回复生成成功 (账号: {cookie_id}): {reply}")
                return reply
            else:
                logger.warning(f"AI回复为空 (账号: {cookie_id})")
                return None
                
        except Exception as e:
            logger.error(f"AI回复生成失败 {cookie_id}: {e}")
            return None


# 全局AI回复引擎实例
ai_reply_engine = AIReplyEngine()