#!/usr/bin/env python3
"""
增强的AI回复引擎
参考XianyuAutoAgent的实现，提供更智能的商品信息感知和回复生成
"""

import time
from typing import List, Dict, Optional, Any
from pathlib import Path
from loguru import logger
from openai import OpenAI
from db_manager import db_manager
from enhanced_item_manager import enhanced_item_manager


class ContextManager:
    """对话上下文管理器"""
    
    def __init__(self):
        self.context_cache = {}  # {chat_id: {'messages': [], 'last_update': float}}
        self.max_context_messages = 10  # 最多保留10条对话记录
        self.context_expire_time = 3600  # 上下文1小时后过期
    
    def add_message(self, chat_id: str, role: str, content: str, item_info: Dict = None):
        """添加消息到上下文"""
        try:
            current_time = time.time()
            
            if chat_id not in self.context_cache:
                self.context_cache[chat_id] = {
                    'messages': [],
                    'last_update': current_time,
                    'item_info': item_info
                }
            
            # 添加新消息
            self.context_cache[chat_id]['messages'].append({
                'role': role,
                'content': content,
                'timestamp': current_time
            })
            
            # 更新商品信息（如果提供）
            if item_info:
                self.context_cache[chat_id]['item_info'] = item_info
            
            self.context_cache[chat_id]['last_update'] = current_time
            
            # 限制消息数量
            messages = self.context_cache[chat_id]['messages']
            if len(messages) > self.max_context_messages:
                self.context_cache[chat_id]['messages'] = messages[-self.max_context_messages:]
                
        except Exception as e:
            logger.error(f"添加上下文消息失败: {e}")
    
    def get_context(self, chat_id: str) -> Dict:
        """获取对话上下文"""
        try:
            if chat_id not in self.context_cache:
                return {'messages': [], 'item_info': None}
            
            context = self.context_cache[chat_id]
            current_time = time.time()
            
            # 检查是否过期
            if current_time - context['last_update'] > self.context_expire_time:
                del self.context_cache[chat_id]
                return {'messages': [], 'item_info': None}
            
            return {
                'messages': context['messages'],
                'item_info': context.get('item_info')
            }
            
        except Exception as e:
            logger.error(f"获取上下文失败: {e}")
            return {'messages': [], 'item_info': None}
    
    def get_negotiation_count(self, chat_id: str) -> int:
        """获取议价次数"""
        try:
            context = self.get_context(chat_id)
            messages = context['messages']
            
            # 计算包含价格相关关键词的消息数量
            price_keywords = ['多少钱', '价格', '便宜', '优惠', '折扣', '砍价', '议价']
            count = 0
            
            for msg in messages:
                if msg['role'] == 'user':
                    content = msg['content'].lower()
                    if any(keyword in content for keyword in price_keywords):
                        count += 1
            
            return count
            
        except Exception as e:
            logger.error(f"获取议价次数失败: {e}")
            return 0


class EnhancedAIReplyEngine:
    """增强的AI回复引擎"""
    
    def __init__(self):
        self.clients = {}  # 存储不同账号的OpenAI客户端
        self.context_manager = ContextManager()
        self.reply_cache = {}  # 回复缓存
        self._init_enhanced_prompts()
    
    def _init_enhanced_prompts(self):
        """初始化增强的提示词"""
        self.enhanced_prompts = {
            'system_base': """你是专业的闲鱼商品客服助手，专门处理商品咨询。你需要基于提供的完整商品信息和对话历史来回复用户。

核心原则：
1. 严格基于提供的商品信息回答，不要编造信息
2. 参考对话历史，保持上下文连贯性
3. 回复要简洁专业，一般不超过50字
4. 针对不同类型咨询采用对应话术

回复策略：
- 价格咨询：明确报价，根据议价次数调整策略
- 商品详情：基于商品属性、标签、描述回答
- 使用方法：参考商品分类和属性说明
- 地区限制：基于商品地区信息回答
- 其他咨询：友好专业回应""",

            'price_negotiation': """基于议价轮次调整策略：
- 首次询价：报出标准价格，态度友好
- 2-3次议价：可以小幅让步，强调品质
- 4次以上：坚持底线价格，说明成本""",

            'product_detail': """基于商品信息回答：
商品属性：{attributes}
商品标签：{tags}
商品分类：{category}
商品描述：{description}

重点突出商品的核心卖点和特色。""",

            'technical_support': """基于商品类型提供技术支持：
- 电子产品：说明使用方法、兼容性、售后
- 餐饮券：说明使用流程、有效期、适用门店
- 其他商品：根据商品属性提供相应指导"""
        }
    
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
                base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
            else:
                base_url = settings.get('base_url', 'https://api.openai.com/v1')
            
            client = OpenAI(
                api_key=settings['api_key'],
                base_url=base_url
            )
            
            self.clients[cookie_id] = client
            logger.info(f"为账号 {cookie_id} 创建AI客户端成功")
            return client
            
        except Exception as e:
            logger.error(f"创建AI客户端失败 {cookie_id}: {e}")
            return None
    
    def _is_dashscope_api(self, settings: dict) -> bool:
        """判断是否为DashScope API"""
        try:
            model_name = settings.get('model_name', '').lower()
            base_url = settings.get('base_url', '').lower()
            
            dashscope_models = [
                'qwen', 'baichuan', 'chatglm', 'llama2', 'llama3',
                'yi', 'internlm', 'deepseek', 'mixtral'
            ]
            
            is_custom_model = any(model in model_name for model in dashscope_models)
            is_dashscope_url = 'dashscope' in base_url or 'aliyun' in base_url
            
            return is_custom_model or is_dashscope_url
            
        except Exception as e:
            logger.error(f"判断API类型失败: {e}")
            return False
    
    async def generate_enhanced_reply(self, message: str, item_id: str, chat_id: str,
                                    cookie_id: str, user_id: str, xianyu_instance) -> Optional[str]:
        """
        生成增强的AI回复
        
        Args:
            message: 用户消息
            item_id: 商品ID  
            chat_id: 对话ID
            cookie_id: Cookie ID
            user_id: 用户ID
            xianyu_instance: XianyuLive实例
            
        Returns:
            AI生成的回复内容
        """
        try:
            # 1. 检查AI是否启用
            settings = db_manager.get_ai_reply_settings(cookie_id)
            if not settings['ai_enabled'] or not settings['api_key']:
                logger.debug(f"账号 {cookie_id} AI回复未启用")
                return None
            
            # 2. 过滤无效消息
            if self._is_invalid_message(message):
                logger.debug(f"过滤无效消息: {message}")
                return None
            
            # 3. 获取增强商品信息
            enhanced_item_info = await enhanced_item_manager.get_enhanced_item_info(
                cookie_id, item_id, xianyu_instance
            )
            
            # 4. 获取对话上下文
            context = self.context_manager.get_context(chat_id)
            
            # 5. 检测用户意图和场景
            intent, scenario_data = await self._detect_intent_and_scenario(
                message, enhanced_item_info, context
            )
            
            # 6. 生成针对性回复
            reply = await self._generate_contextual_reply(
                message=message,
                enhanced_item_info=enhanced_item_info,
                context=context,
                intent=intent,
                scenario_data=scenario_data,
                settings=settings,
                cookie_id=cookie_id
            )
            
            # 7. 更新对话上下文
            self.context_manager.add_message(chat_id, 'user', message, enhanced_item_info)
            if reply:
                self.context_manager.add_message(chat_id, 'assistant', reply)
            
            logger.info(f"增强AI回复生成成功: {reply}")
            return reply
            
        except Exception as e:
            logger.error(f"生成增强AI回复失败: {e}")
            return None
    
    async def _detect_intent_and_scenario(self, message: str, item_info: Dict, 
                                        context: Dict) -> tuple:
        """检测用户意图和场景"""
        try:
            message_lower = message.lower().strip()
            
            # 场景数据
            scenario_data = {
                'negotiation_count': self.context_manager.get_negotiation_count(
                    context.get('chat_id', '')
                ),
                'item_category': item_info.get('category', ''),
                'item_price': item_info.get('price', ''),
                'item_tags': item_info.get('tags', []),
                'conversation_length': len(context.get('messages', []))
            }
            
            # 价格意图检测
            price_keywords = ['多少钱', '价格', '费用', '收费', '钱', '元', '块', '便宜', '优惠']
            if any(keyword in message_lower for keyword in price_keywords):
                return 'price', scenario_data
            
            # 技术/使用意图检测
            tech_keywords = ['怎么用', '如何使用', '使用方法', '操作', '步骤', '兼容', '支持']
            if any(keyword in message_lower for keyword in tech_keywords):
                return 'technical', scenario_data
            
            # 商品详情意图检测
            detail_keywords = ['属性', '规格', '参数', '材质', '尺寸', '颜色', '型号']
            if any(keyword in message_lower for keyword in detail_keywords):
                return 'product_detail', scenario_data
            
            # 地区/门店意图检测
            location_keywords = ['门店', '地址', '位置', '哪里', '在哪', '能用吗', '支持']
            if any(keyword in message_lower for keyword in location_keywords):
                return 'location', scenario_data
            
            return 'general', scenario_data
            
        except Exception as e:
            logger.error(f"意图检测失败: {e}")
            return 'general', {}
    
    async def _generate_contextual_reply(self, message: str, enhanced_item_info: Dict,
                                       context: Dict, intent: str, scenario_data: Dict,
                                       settings: Dict, cookie_id: str) -> Optional[str]:
        """基于上下文生成回复"""
        try:
            client = self.get_client(cookie_id)
            if not client:
                return None
            
            # 构建增强的系统提示词
            system_prompt = self._build_enhanced_system_prompt(
                enhanced_item_info, intent, scenario_data
            )
            
            # 构建对话历史
            messages = [{"role": "system", "content": system_prompt}]
            
            # 添加历史对话（最近5轮）
            history_messages = context.get('messages', [])[-10:]  # 最近10条消息
            for hist_msg in history_messages:
                if hist_msg['role'] in ['user', 'assistant']:
                    messages.append({
                        "role": hist_msg['role'], 
                        "content": hist_msg['content']
                    })
            
            # 添加当前用户消息
            messages.append({"role": "user", "content": message})
            
            # 根据意图调整温度参数
            temperature = self._get_temperature_by_intent(intent, scenario_data)
            
            # 调用AI生成回复
            response = client.chat.completions.create(
                model=settings.get('model_name', 'gpt-3.5-turbo'),
                messages=messages,
                max_tokens=200,
                temperature=temperature
            )
            
            reply = response.choices[0].message.content.strip()
            logger.info(f"上下文AI回复生成成功 (意图: {intent})")
            return reply
            
        except Exception as e:
            logger.error(f"上下文AI回复生成失败: {e}")
            return None
    
    def _build_enhanced_system_prompt(self, item_info: Dict, intent: str, 
                                    scenario_data: Dict) -> str:
        """构建增强的系统提示词"""
        try:
            base_prompt = self.enhanced_prompts['system_base']
            
            # 商品信息部分
            item_context = f"""
当前咨询商品信息：
标题：{item_info.get('title', '未知商品')}
价格：{item_info.get('price', '面议')}
分类：{item_info.get('category', '未知分类')}
描述：{item_info.get('description', '暂无描述')}
地区：{item_info.get('area', '位置未知')}
商品属性：{', '.join(str(attr) for attr in item_info.get('attributes', []))}
商品标签：{', '.join(item_info.get('tags', []))}
卖家：{item_info.get('seller_name', '匿名卖家')}
"""
            
            # 场景信息
            scenario_context = f"""
对话场景信息：
议价轮次：{scenario_data.get('negotiation_count', 0)}
对话长度：{scenario_data.get('conversation_length', 0)}
当前意图：{intent}
"""
            
            # 根据意图添加特定指导
            intent_guidance = ""
            if intent == 'price':
                negotiation_count = scenario_data.get('negotiation_count', 0)
                if negotiation_count == 1:
                    intent_guidance = "这是首次价格咨询，态度友好地报出价格，可以简单说明商品价值。"
                elif negotiation_count <= 3:
                    intent_guidance = "这是多次议价，可以适当让步，但要强调商品品质和成本。"
                else:
                    intent_guidance = "议价次数较多，坚持合理价格，说明底线。"
            
            elif intent == 'technical':
                category = scenario_data.get('item_category', '')
                if '餐饮' in category or '券' in category:
                    intent_guidance = "这是餐饮券使用咨询，说明使用流程：①拍下立即发券码 ②查看使用说明 ③按说明兑换。"
                else:
                    intent_guidance = "根据商品类型说明使用方法和注意事项。"
            
            elif intent == 'location':
                intent_guidance = f"关于使用地区，商品信息显示：{item_info.get('area', '位置未知')}。请基于此信息回答。"
            
            # 组合完整提示词
            full_prompt = f"""{base_prompt}

{item_context}

{scenario_context}

{intent_guidance}

请基于以上信息，简洁专业地回复用户咨询。回复要点：
1. 直接回答用户问题
2. 基于真实商品信息
3. 考虑对话上下文
4. 保持专业友好语气
5. 回复长度控制在50字以内"""
            
            return full_prompt
            
        except Exception as e:
            logger.error(f"构建系统提示词失败: {e}")
            return self.enhanced_prompts['system_base']
    
    def _get_temperature_by_intent(self, intent: str, scenario_data: Dict) -> float:
        """根据意图获取温度参数"""
        try:
            # 价格咨询需要更稳定的回复
            if intent == 'price':
                negotiation_count = scenario_data.get('negotiation_count', 0)
                if negotiation_count > 3:
                    return 0.1  # 多次议价，回复要稳定
                return 0.3
            
            # 技术支持需要准确性
            elif intent == 'technical':
                return 0.2
            
            # 商品详情需要准确
            elif intent == 'product_detail':
                return 0.2
            
            # 地区咨询需要准确
            elif intent == 'location':
                return 0.1
            
            # 一般咨询可以稍微灵活一些
            else:
                return 0.5
                
        except Exception as e:
            logger.error(f"获取温度参数失败: {e}")
            return 0.3
    
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


# 全局增强AI回复引擎实例
enhanced_ai_reply_engine = EnhancedAIReplyEngine()