#!/usr/bin/env python3
"""
增强AI回复引擎 v2
保持现有提示词不变，增强商品信息利用和上下文管理能力
专注于技术改进，不修改提示词内容
"""

import time
from typing import List, Dict, Optional, Any
from pathlib import Path
from loguru import logger
from openai import OpenAI
from db_manager import db_manager
from enhanced_db_manager import enhanced_db_manager
from enhanced_item_manager import enhanced_item_manager


class ContextManager:
    """对话上下文管理器"""
    
    def __init__(self):
        self.context_expire_time = 3600  # 上下文1小时后过期
    
    def add_message(self, chat_id: str, cookie_id: str, user_id: str, 
                   role: str, content: str, item_id: str = '', intent: str = 'general'):
        """添加消息到上下文"""
        try:
            # 获取现有上下文
            context = enhanced_db_manager.get_conversation_context(chat_id, self.context_expire_time)
            
            if context:
                # 检测议价行为
                if role == 'user' and intent == 'price':
                    negotiation_count = context.get('negotiation_count', 0) + 1
                else:
                    negotiation_count = context.get('negotiation_count', 0)
                
                # 添加新消息到历史
                message_history = context.get('message_history', [])
                message_history.append({
                    'role': role,
                    'content': content,
                    'timestamp': time.time(),
                    'intent': intent
                })
                
                # 限制消息数量（保留最近10条）
                if len(message_history) > 10:
                    message_history = message_history[-10:]
                
                # 更新上下文
                enhanced_db_manager.save_conversation_context(
                    chat_id=chat_id,
                    cookie_id=cookie_id,
                    user_id=user_id,
                    item_id=item_id,
                    message_history=message_history,
                    negotiation_count=negotiation_count,
                    last_intent=intent
                )
            else:
                # 创建新的上下文
                message_history = [{
                    'role': role,
                    'content': content,
                    'timestamp': time.time(),
                    'intent': intent
                }]
                
                enhanced_db_manager.save_conversation_context(
                    chat_id=chat_id,
                    cookie_id=cookie_id,
                    user_id=user_id,
                    item_id=item_id,
                    message_history=message_history,
                    negotiation_count=1 if (role == 'user' and intent == 'price') else 0,
                    last_intent=intent
                )
                
        except Exception as e:
            logger.error(f"添加上下文消息失败: {e}")
    
    def get_context(self, chat_id: str) -> Dict:
        """获取对话上下文"""
        try:
            context = enhanced_db_manager.get_conversation_context(chat_id, self.context_expire_time)
            if context:
                return {
                    'messages': context.get('message_history', []),
                    'negotiation_count': context.get('negotiation_count', 0),
                    'last_intent': context.get('last_intent', 'general'),
                    'item_id': context.get('item_id', '')
                }
            return {'messages': [], 'negotiation_count': 0, 'last_intent': 'general', 'item_id': ''}
        except Exception as e:
            logger.error(f"获取上下文失败: {e}")
            return {'messages': [], 'negotiation_count': 0, 'last_intent': 'general', 'item_id': ''}


class EnhancedAIReplyEngineV2:
    """增强AI回复引擎 v2 - 保持现有提示词不变"""
    
    def __init__(self):
        self.clients = {}  # 存储不同账号的OpenAI客户端
        self.reply_cache = {}  # 回复缓存
        self.context_manager = ContextManager()
        self._init_prompts()
    
    def _init_prompts(self):
        """初始化提示词 - 完全保持原有逻辑"""
        self.prompts = {}
        prompts_dir = Path('prompts')
        
        # 定义提示词文件映射 - 与原版完全一致
        prompt_files = {
            'classify': 'classify_prompt.txt',
            'price': 'price_prompt.txt', 
            'tech': 'tech_prompt.txt',
            'default': 'default_prompt.txt',
            'store': 'store_prompt.txt'
        }
        
        # 加载提示词文件 - 与原版完全一致
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
        """获取默认提示词 - 与原版完全一致"""
        defaults = {
            'classify': "请分析用户消息的意图，返回：price（价格询问）、tech（使用方法）、store（门店查询）、default（其他）",
            'price': "用户询问价格，请回复：券码价格¥25.8，固定不议价",
            'tech': "用户询问使用方法，请回复：①拍下秒发券码 ②详情页第2、3张图有使用说明",
            'store': "用户询问门店，请回复：请查看详情页门店列表确认是否可用",
            'default': "感谢咨询，有任何问题随时联系我们"
        }
        return defaults.get(prompt_type, "抱歉，暂时无法处理您的问题")
    
    def get_client(self, cookie_id: str) -> Optional[OpenAI]:
        """获取或创建OpenAI客户端 - 与原版完全一致"""
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
                logger.info(f"创建DashScope客户端 {cookie_id}: base_url={base_url}")
            else:
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
        """判断是否为DashScope API - 与原版完全一致"""
        try:
            model_name = settings.get('model_name', '').lower()
            base_url = settings.get('base_url', '').lower()
            
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
        """检查是否为无效消息 - 与原版一致"""
        if not message or len(message.strip()) == 0:
            return True
        
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
        """基于规则的意图检测 - 与原版一致"""
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
        """检测用户意图 - 与原版一致"""
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
    
    async def generate_enhanced_reply(self, message: str, item_id: str, chat_id: str,
                                    cookie_id: str, user_id: str, xianyu_instance) -> Optional[str]:
        """
        生成增强AI回复
        核心改进：使用增强商品信息，但保持原有提示词不变
        """
        try:
            # 1. 检查是否启用AI回复
            if not self.is_ai_enabled(cookie_id):
                logger.debug(f"账号 {cookie_id} AI回复未启用")
                return None
            
            # 2. 过滤无效消息
            if self._is_invalid_message(message):
                logger.debug(f"过滤无效消息: {message}")
                return None
            
            # 3. 检测用户意图
            intent = self.detect_intent(message, cookie_id)
            logger.info(f"检测到意图: {intent} (账号: {cookie_id})")
            
            # 4. 获取增强商品信息
            enhanced_item_info = await enhanced_item_manager.get_enhanced_item_info(
                cookie_id, item_id, xianyu_instance
            )
            
            # 5. 获取对话上下文
            context = self.context_manager.get_context(chat_id)
            
            # 6. 添加用户消息到上下文
            self.context_manager.add_message(
                chat_id, cookie_id, user_id, 'user', message, item_id, intent
            )
            
            # 7. 处理特殊场景（与原版逻辑保持一致）
            special_reply = await self._handle_special_cases(
                message, enhanced_item_info, intent, context, user_id
            )
            if special_reply:
                # 添加AI回复到上下文
                self.context_manager.add_message(
                    chat_id, cookie_id, user_id, 'assistant', special_reply, item_id, intent
                )
                return special_reply
            
            # 8. 检查重复回复缓存
            cache_key = f"{chat_id}_{user_id}_{hash(message)}"
            if cache_key in self.reply_cache:
                cached_time = self.reply_cache[cache_key]['time']
                if time.time() - cached_time < 300:  # 5分钟内不重复回复
                    logger.debug(f"跳过重复回复: {message}")
                    return None
            
            # 9. 生成AI回复
            reply = await self._generate_enhanced_ai_reply(
                message, enhanced_item_info, intent, context, cookie_id
            )
            
            if reply:
                # 10. 缓存回复
                self.reply_cache[cache_key] = {
                    'reply': reply,
                    'time': time.time()
                }
                
                # 11. 添加AI回复到上下文
                self.context_manager.add_message(
                    chat_id, cookie_id, user_id, 'assistant', reply, item_id, intent
                )
                
                logger.info(f"增强AI回复生成成功: {reply}")
                return reply
            
            return None
            
        except Exception as e:
            logger.error(f"生成增强AI回复失败: {e}")
            return None
    
    async def _handle_special_cases(self, message: str, enhanced_item_info: Dict, 
                                   intent: str, context: Dict, user_id: str) -> Optional[str]:
        """处理特殊场景 - 保持与原版逻辑一致"""
        try:
            message_lower = message.lower().strip()
            
            # 价格询问 - 使用增强商品信息但保持回复逻辑
            if intent == 'price' or any(word in message_lower for word in ['多少钱', '价格', '多少']):
                price = enhanced_item_info.get('price', '面议')
                if price and price != '面议':
                    return f"券码价格{price}，固定不议价"
                else:
                    return "券码价格¥25.8，固定不议价"
            
            # 使用方法询问
            if intent == 'tech' or any(word in message_lower for word in ['怎么用', '如何使用', '使用方法']):
                return "①拍下秒发券码 ②详情页第2、3张图有使用说明"
            
            # 门店查询 - 利用增强的地区信息
            if intent == 'store' or any(word in message_lower for word in ['门店', '地址', '能用吗']):
                area = enhanced_item_info.get('area', '')
                if area and area != '位置未知':
                    return f"支持{area}使用，详细门店请查看详情页门店列表确认"
                else:
                    return "请查看详情页门店列表确认是否可用"
            
            # 退款相关
            if any(word in message_lower for word in ['退款', '退货', '不要了']):
                return "未使用可申请退款，已使用无法退款"
            
            # 系统消息过滤
            if message_lower in ['[去支付]', '[立即购买]', '[确认收货]']:
                return None
            
            return None
            
        except Exception as e:
            logger.error(f"处理特殊场景失败: {e}")
            return None
    
    async def _generate_enhanced_ai_reply(self, message: str, enhanced_item_info: Dict,
                                        intent: str, context: Dict, cookie_id: str) -> Optional[str]:
        """生成增强的AI回复 - 使用增强商品信息构建上下文，但保持提示词不变"""
        try:
            client = self.get_client(cookie_id)
            if not client:
                return None
            
            settings = db_manager.get_ai_reply_settings(cookie_id)
            
            # 根据意图选择提示词（与原版逻辑保持一致）
            if intent == 'price':
                # 价格询问直接返回固定回复
                price = enhanced_item_info.get('price', '¥25.8')
                return f"券码价格{price}，固定不议价"
                
            elif intent in ['tech', 'store', 'default']:
                # 选择对应的提示词
                prompt_key = intent if intent in self.prompts else 'default'
                system_prompt = self.prompts[prompt_key]
                
                # 构建增强的商品上下文信息
                enhanced_context = self._build_enhanced_context(enhanced_item_info, context)
                
                # 判断API类型并调用
                if self._is_dashscope_api(settings):
                    logger.info("使用DashScope API生成回复")
                    response = client.chat.completions.create(
                        model=settings.get('model_name', 'qwen-turbo'),
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": enhanced_context}
                        ],
                        max_tokens=200,
                        temperature=self._get_temperature_by_context(intent, context)
                    )
                else:
                    logger.info("使用OpenAI兼容API生成回复")
                    response = client.chat.completions.create(
                        model=settings.get('model_name', 'gpt-3.5-turbo'),
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": enhanced_context}
                        ],
                        max_tokens=200,
                        temperature=self._get_temperature_by_context(intent, context)
                    )
                
                reply = response.choices[0].message.content.strip()
                
                if reply:
                    logger.info(f"AI回复生成成功 (账号: {cookie_id}, 意图: {intent}): {reply}")
                    return reply
            
            return None
            
        except Exception as e:
            logger.error(f"AI回复生成失败 {cookie_id}: {e}")
            return None
    
    def _build_enhanced_context(self, enhanced_item_info: Dict, context: Dict) -> str:
        """构建增强的上下文信息"""
        try:
            # 基础商品信息
            title = enhanced_item_info.get('title', '未知商品')
            price = enhanced_item_info.get('price', '面议')
            description = enhanced_item_info.get('description', '暂无描述')
            
            # 增强信息
            category = enhanced_item_info.get('category', '未知分类')
            area = enhanced_item_info.get('area', '位置未知')
            attributes = enhanced_item_info.get('attributes', [])
            tags = enhanced_item_info.get('tags', [])
            
            # 对话上下文
            negotiation_count = context.get('negotiation_count', 0)
            recent_messages = context.get('messages', [])[-3:]  # 最近3条消息
            
            # 构建上下文字符串
            context_parts = []
            
            # 商品信息部分
            context_parts.append(f"商品标题：{title}")
            context_parts.append(f"商品价格：{price}")
            
            if category and category != '未知分类':
                context_parts.append(f"商品分类：{category}")
            
            if area and area != '位置未知':
                context_parts.append(f"使用地区：{area}")
            
            if attributes:
                context_parts.append(f"商品属性：{', '.join(str(attr) for attr in attributes)}")
            
            if tags:
                context_parts.append(f"商品标签：{', '.join(tags)}")
            
            if description and description != '暂无描述':
                context_parts.append(f"商品描述：{description}")
            
            # 对话上下文部分
            if negotiation_count > 0:
                context_parts.append(f"议价次数：{negotiation_count}")
            
            if recent_messages:
                context_parts.append("最近对话：")
                for msg in recent_messages:
                    role_name = "用户" if msg.get('role') == 'user' else "客服"
                    context_parts.append(f"- {role_name}: {msg.get('content', '')}")
            
            return "\n".join(context_parts)
            
        except Exception as e:
            logger.error(f"构建增强上下文失败: {e}")
            # 返回基础上下文
            return f"""
商品信息：
- 标题：{enhanced_item_info.get('title', '未知商品')}
- 价格：{enhanced_item_info.get('price', '面议')}
- 描述：{enhanced_item_info.get('description', '暂无描述')}
"""
    
    def _get_temperature_by_context(self, intent: str, context: Dict) -> float:
        """根据上下文获取温度参数"""
        try:
            negotiation_count = context.get('negotiation_count', 0)
            
            # 价格咨询需要更稳定的回复
            if intent == 'price':
                if negotiation_count > 3:
                    return 0.1  # 多次议价，回复要稳定
                return 0.3
            
            # 技术支持需要准确性
            elif intent == 'tech':
                return 0.2
            
            # 门店查询需要准确
            elif intent == 'store':
                return 0.1
            
            # 一般咨询可以稍微灵活一些
            else:
                return 0.5
                
        except Exception as e:
            logger.error(f"获取温度参数失败: {e}")
            return 0.3


# 全局增强AI回复引擎实例
enhanced_ai_reply_engine_v2 = EnhancedAIReplyEngineV2()