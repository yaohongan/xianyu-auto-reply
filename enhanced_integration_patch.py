#!/usr/bin/env python3
"""
增强功能集成补丁
将增强的商品信息管理和AI回复引擎集成到现有的XianyuAutoAsync中
"""

from loguru import logger


class EnhancedIntegrationPatch:
    """增强功能集成补丁"""
    
    @staticmethod
    def apply_enhanced_ai_reply(xianyu_instance):
        """应用增强AI回复功能的补丁"""
        
        async def get_enhanced_ai_reply(self, send_user_name: str, send_user_id: str, 
                                       send_message: str, item_id: str, chat_id: str):
            """
            获取增强AI回复 - 替换原有的get_ai_reply方法
            
            主要改进：
            1. 使用增强商品信息管理器获取完整商品信息
            2. 使用增强AI回复引擎生成更智能的回复
            3. 支持上下文感知对话
            """
            try:
                # 检查是否启用增强AI功能
                from config import config
                use_enhanced_ai = config.get('AI_REPLY', {}).get('use_enhanced', True)
                
                if use_enhanced_ai:
                    # 使用增强AI回复引擎
                    from enhanced_ai_reply_engine import enhanced_ai_reply_engine
                    
                    # 检查是否启用AI回复
                    if not enhanced_ai_reply_engine.context_manager:
                        logger.debug(f"账号 {self.cookie_id} 增强AI回复未初始化")
                        return await self._fallback_to_original_ai_reply(
                            send_user_name, send_user_id, send_message, item_id, chat_id
                        )
                    
                    # 使用增强AI回复引擎生成回复
                    reply = await enhanced_ai_reply_engine.generate_enhanced_reply(
                        message=send_message,
                        item_id=item_id,
                        chat_id=chat_id,
                        cookie_id=self.cookie_id,
                        user_id=send_user_id,
                        xianyu_instance=self
                    )
                    
                    if reply:
                        logger.info(f"增强AI回复生成成功: {reply[:50]}...")
                        return reply
                    else:
                        # 回退到原始AI回复
                        logger.info("增强AI回复失败，回退到原始AI回复")
                        return await self._fallback_to_original_ai_reply(
                            send_user_name, send_user_id, send_message, item_id, chat_id
                        )
                
                else:
                    # 使用原始AI回复
                    return await self._fallback_to_original_ai_reply(
                        send_user_name, send_user_id, send_message, item_id, chat_id
                    )
                    
            except Exception as e:
                logger.error(f"增强AI回复异常: {e}，回退到原始回复")
                return await self._fallback_to_original_ai_reply(
                    send_user_name, send_user_id, send_message, item_id, chat_id
                )
        
        async def _fallback_to_original_ai_reply(self, send_user_name: str, send_user_id: str, 
                                               send_message: str, item_id: str, chat_id: str):
            """回退到原始AI回复逻辑"""
            try:
                from ai_reply_engine import ai_reply_engine
                from db_manager import db_manager
                
                # 检查是否启用AI回复
                if not ai_reply_engine.is_ai_enabled(self.cookie_id):
                    logger.debug(f"账号 {self.cookie_id} 未启用AI回复")
                    return None

                # 从数据库获取商品信息
                item_info_raw = db_manager.get_item_info(self.cookie_id, item_id)

                if not item_info_raw:
                    logger.debug(f"数据库中无商品信息: {item_id}")
                    # 尝试实时获取商品信息
                    try:
                        item_detail = await self.get_item_detail(item_id)
                        if item_detail and 'item_title' in item_detail:
                            item_info = {
                                'title': item_detail.get('item_title', '未知商品'),
                                'price': self._parse_price(item_detail.get('item_price', '面议')),
                                'desc': item_detail.get('item_description', '暂无商品描述')
                            }
                            logger.info(f"实时获取商品信息成功: {item_info['title']}")
                        else:
                            # 使用默认商品信息
                            item_info = {
                                'title': '餐饮券商品',
                                'price': '面议',
                                'desc': '详细信息请查看商品详情页'
                            }
                            logger.debug(f"使用默认商品信息")
                    except Exception as e:
                        logger.warning(f"实时获取商品信息失败: {e}")
                        item_info = {
                            'title': '餐饮券商品',
                            'price': '面议',
                            'desc': '详细信息请查看商品详情页'
                        }
                else:
                    # 解析数据库中的商品信息
                    item_info = {
                        'title': item_info_raw.get('item_title', '未知商品'),
                        'price': self._parse_price(item_info_raw.get('item_price', '0')),
                        'desc': item_info_raw.get('item_description', '暂无商品描述')
                    }

                # 生成AI回复
                reply = ai_reply_engine.generate_reply(
                    message=send_message,
                    item_info=item_info,
                    chat_id=chat_id,
                    cookie_id=self.cookie_id,
                    user_id=send_user_id,
                    item_id=item_id
                )

                if reply:
                    logger.info(f"原始AI回复生成成功: {reply}")
                    return reply
                else:
                    logger.debug("AI回复生成失败或无回复")
                    return None
                    
            except Exception as e:
                logger.error(f"原始AI回复异常: {e}")
                return None
        
        # 动态替换方法
        import types
        xianyu_instance.get_ai_reply = types.MethodType(get_enhanced_ai_reply, xianyu_instance)
        xianyu_instance._fallback_to_original_ai_reply = types.MethodType(_fallback_to_original_ai_reply, xianyu_instance)
        
        logger.info(f"已为账号 {xianyu_instance.cookie_id} 应用增强AI回复补丁")
    
    @staticmethod
    def apply_enhanced_item_management(xianyu_instance):
        """应用增强商品信息管理的补丁"""
        
        async def get_enhanced_item_detail(self, item_id: str):
            """
            获取增强商品详情 - 增强版本的商品详情获取
            
            主要改进：
            1. 使用增强商品信息管理器
            2. 支持完整商品信息缓存
            3. 更好的错误处理和回退机制
            """
            try:
                # 检查是否启用增强商品管理
                from config import config
                use_enhanced_item = config.get('ITEM_MANAGEMENT', {}).get('use_enhanced', True)
                
                if use_enhanced_item:
                    from enhanced_item_manager import enhanced_item_manager
                    
                    # 使用增强商品信息管理器获取详情
                    enhanced_info = await enhanced_item_manager.get_enhanced_item_info(
                        self.cookie_id, item_id, self
                    )
                    
                    if enhanced_info and enhanced_info.get('enhanced'):
                        logger.info(f"增强商品信息获取成功: {enhanced_info.get('title', 'Unknown')}")
                        return enhanced_info
                    else:
                        # 回退到原始方法
                        logger.debug("增强商品信息获取失败，使用原始方法")
                        return await self._original_get_item_detail(item_id)
                else:
                    return await self._original_get_item_detail(item_id)
                    
            except Exception as e:
                logger.error(f"增强商品详情获取异常: {e}")
                return await self._original_get_item_detail(item_id)
        
        # 保存原始方法
        xianyu_instance._original_get_item_detail = xianyu_instance.get_item_detail
        
        # 动态替换方法
        import types
        xianyu_instance.get_item_detail = types.MethodType(get_enhanced_item_detail, xianyu_instance)
        
        logger.info(f"已为账号 {xianyu_instance.cookie_id} 应用增强商品管理补丁")
    
    @staticmethod
    def apply_all_enhancements(xianyu_instance):
        """应用所有增强功能"""
        try:
            # 应用增强商品管理
            EnhancedIntegrationPatch.apply_enhanced_item_management(xianyu_instance)
            
            # 应用增强AI回复
            EnhancedIntegrationPatch.apply_enhanced_ai_reply(xianyu_instance)
            
            logger.info(f"所有增强功能已成功应用到账号 {xianyu_instance.cookie_id}")
            
        except Exception as e:
            logger.error(f"应用增强功能失败: {e}")


# 自动应用补丁的装饰器
def apply_enhancements(cls):
    """装饰器：自动为XianyuLive类应用增强功能"""
    
    original_init = cls.__init__
    
    def enhanced_init(self, *args, **kwargs):
        # 调用原始初始化
        original_init(self, *args, **kwargs)
        
        # 应用增强功能
        try:
            EnhancedIntegrationPatch.apply_all_enhancements(self)
        except Exception as e:
            logger.warning(f"应用增强功能时出现警告: {e}")
    
    cls.__init__ = enhanced_init
    return cls