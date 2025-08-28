#!/usr/bin/env python3
"""
智能集成补丁
无侵入式地将增强功能集成到现有的XianyuAutoAsync中
保持现有提示词和接口完全不变
"""

import types
import asyncio
from loguru import logger
from enhanced_ai_reply_engine_v2 import enhanced_ai_reply_engine_v2
from enhanced_item_manager import enhanced_item_manager
from enhanced_db_manager import enhanced_db_manager


class SmartIntegrationPatch:
    """智能集成补丁"""
    
    @staticmethod
    def apply_patches(xianyu_instance):
        """应用所有补丁到XianyuLive实例"""
        try:
            # 应用AI回复增强补丁
            SmartIntegrationPatch._patch_ai_reply(xianyu_instance)
            
            # 应用商品信息获取增强补丁
            SmartIntegrationPatch._patch_item_info_fetching(xianyu_instance)
            
            # 初始化增强数据库表
            SmartIntegrationPatch._init_enhanced_database()
            
            logger.info(f"✅ 智能增强补丁已应用到账号 {xianyu_instance.cookie_id}")
            
        except Exception as e:
            logger.error(f"❌ 应用智能增强补丁失败: {e}")
    
    @staticmethod
    def _patch_ai_reply(xianyu_instance):
        """补丁：增强AI回复功能"""
        
        # 保存原始方法
        original_get_ai_reply = xianyu_instance.get_ai_reply if hasattr(xianyu_instance, 'get_ai_reply') else None
        
        async def enhanced_get_ai_reply(self, send_user_name: str, send_user_id: str, 
                                       send_message: str, item_id: str, chat_id: str):
            """增强版AI回复方法"""
            try:
                # 检查是否启用增强功能
                use_enhanced = SmartIntegrationPatch._check_enhanced_enabled()
                
                if use_enhanced:
                    # 使用增强AI回复引擎
                    logger.debug(f"使用增强AI回复引擎处理消息: {send_message[:50]}...")
                    
                    reply = await enhanced_ai_reply_engine_v2.generate_enhanced_reply(
                        message=send_message,
                        item_id=item_id,
                        chat_id=chat_id,
                        cookie_id=self.cookie_id,
                        user_id=send_user_id,
                        xianyu_instance=self
                    )
                    
                    if reply:
                        logger.info(f"✅ 增强AI回复生成成功: {reply[:100]}...")
                        return reply
                    else:
                        logger.debug("增强AI回复返回None，尝试回退到原始方法")
                        
                # 回退到原始方法（如果存在）
                if original_get_ai_reply:
                    logger.debug("回退到原始AI回复方法")
                    return await original_get_ai_reply(send_user_name, send_user_id, send_message, item_id, chat_id)
                else:
                    # 如果没有原始方法，使用基础回复逻辑
                    return await SmartIntegrationPatch._fallback_ai_reply(
                        self, send_user_name, send_user_id, send_message, item_id, chat_id
                    )
                    
            except Exception as e:
                logger.error(f"增强AI回复异常: {e}")
                # 异常时回退
                if original_get_ai_reply:
                    try:
                        return await original_get_ai_reply(send_user_name, send_user_id, send_message, item_id, chat_id)
                    except:
                        pass
                return None
        
        # 动态替换方法
        xianyu_instance.get_ai_reply = types.MethodType(enhanced_get_ai_reply, xianyu_instance)
        xianyu_instance._original_get_ai_reply = original_get_ai_reply
        
        logger.debug(f"AI回复方法已增强: {xianyu_instance.cookie_id}")
    
    @staticmethod
    def _patch_item_info_fetching(xianyu_instance):
        """补丁：增强商品信息获取"""
        
        # 保存原始方法
        original_get_item_detail = getattr(xianyu_instance, 'get_item_detail', None)
        
        async def enhanced_get_item_detail(self, item_id: str):
            """增强版商品详情获取"""
            try:
                # 检查是否启用增强功能
                use_enhanced = SmartIntegrationPatch._check_enhanced_enabled()
                
                if use_enhanced:
                    logger.debug(f"使用增强商品信息管理器获取详情: {item_id}")
                    
                    # 尝试获取增强商品信息
                    enhanced_info = await enhanced_item_manager.get_enhanced_item_info(
                        self.cookie_id, item_id, self
                    )
                    
                    if enhanced_info and enhanced_info.get('enhanced'):
                        logger.debug(f"✅ 获取增强商品信息成功: {enhanced_info.get('title', 'Unknown')}")
                        return {
                            'item_id': item_id,
                            'item_title': enhanced_info.get('title', ''),
                            'item_price': enhanced_info.get('price', ''),
                            'item_description': enhanced_info.get('description', ''),
                            'enhanced_info': enhanced_info  # 添加增强信息
                        }
                
                # 回退到原始方法
                if original_get_item_detail:
                    logger.debug(f"回退到原始商品详情获取方法: {item_id}")
                    return await original_get_item_detail(item_id)
                else:
                    logger.debug(f"没有原始商品详情获取方法，返回基础信息: {item_id}")
                    return {
                        'item_id': item_id,
                        'item_title': '未知商品',
                        'item_price': '面议',
                        'item_description': '暂无描述'
                    }
                    
            except Exception as e:
                logger.error(f"增强商品详情获取异常: {e}")
                if original_get_item_detail:
                    try:
                        return await original_get_item_detail(item_id)
                    except:
                        pass
                return None
        
        # 动态替换方法
        xianyu_instance.get_item_detail = types.MethodType(enhanced_get_item_detail, xianyu_instance)
        xianyu_instance._original_get_item_detail = original_get_item_detail
        
        logger.debug(f"商品详情获取方法已增强: {xianyu_instance.cookie_id}")
    
    @staticmethod
    async def _fallback_ai_reply(xianyu_instance, send_user_name: str, send_user_id: str, 
                                send_message: str, item_id: str, chat_id: str):
        """回退的AI回复逻辑"""
        try:
            # 基础的AI回复逻辑
            from ai_reply_engine import ai_reply_engine
            from db_manager import db_manager
            
            # 检查是否启用AI回复
            if not ai_reply_engine.is_ai_enabled(xianyu_instance.cookie_id):
                logger.debug(f"账号 {xianyu_instance.cookie_id} 未启用AI回复")
                return None

            # 从数据库获取商品信息
            item_info_raw = db_manager.get_item_info(xianyu_instance.cookie_id, item_id)

            if not item_info_raw:
                logger.debug(f"数据库中无商品信息: {item_id}")
                # 使用默认商品信息
                item_info = {
                    'title': '餐饮券商品',
                    'price': '面议',
                    'desc': '详细信息请查看商品详情页'
                }
            else:
                # 解析数据库中的商品信息
                item_info = {
                    'title': item_info_raw.get('item_title', '未知商品'),
                    'price': xianyu_instance._parse_price(item_info_raw.get('item_price', '0')) if hasattr(xianyu_instance, '_parse_price') else item_info_raw.get('item_price', '0'),
                    'desc': item_info_raw.get('item_description', '暂无商品描述')
                }

            # 生成AI回复
            reply = ai_reply_engine.generate_reply(
                message=send_message,
                item_info=item_info,
                chat_id=chat_id,
                cookie_id=xianyu_instance.cookie_id,
                user_id=send_user_id,
                item_id=item_id
            )

            if reply:
                logger.info(f"回退AI回复生成成功: {reply}")
                return reply
            else:
                logger.debug("回退AI回复生成失败或无回复")
                return None
                
        except Exception as e:
            logger.error(f"回退AI回复异常: {e}")
            return None
    
    @staticmethod
    def _check_enhanced_enabled() -> bool:
        """检查是否启用增强功能"""
        try:
            from config import config
            
            # 检查增强AI回复
            ai_enhanced = config.get('AI_REPLY', {}).get('use_enhanced', True)
            
            # 检查增强商品管理
            item_enhanced = config.get('ITEM_MANAGEMENT', {}).get('use_enhanced', True)
            
            return ai_enhanced or item_enhanced
            
        except Exception as e:
            logger.debug(f"检查增强功能配置失败，默认启用: {e}")
            return True  # 默认启用
    
    @staticmethod
    def _init_enhanced_database():
        """初始化增强数据库表"""
        try:
            # 通过导入自动初始化增强数据库表
            _ = enhanced_db_manager
            logger.debug("增强数据库表已初始化")
        except Exception as e:
            logger.error(f"初始化增强数据库表失败: {e}")


def apply_smart_enhancements(cls):
    """装饰器：自动为XianyuLive类应用智能增强功能"""
    
    original_init = cls.__init__
    
    def enhanced_init(self, *args, **kwargs):
        # 调用原始初始化
        original_init(self, *args, **kwargs)
        
        # 延迟应用增强功能，避免初始化冲突
        async def delayed_patch():
            try:
                await asyncio.sleep(0.1)  # 短暂延迟确保初始化完成
                SmartIntegrationPatch.apply_patches(self)
            except Exception as e:
                logger.warning(f"延迟应用增强功能时出现问题: {e}")
        
        # 在事件循环中应用补丁
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 如果事件循环正在运行，使用create_task
                asyncio.create_task(delayed_patch())
            else:
                # 如果事件循环未运行，直接同步应用
                SmartIntegrationPatch.apply_patches(self)
        except Exception as e:
            logger.warning(f"应用智能增强功能时出现问题: {e}")
            # 如果异步应用失败，尝试同步应用
            try:
                SmartIntegrationPatch.apply_patches(self)
            except Exception as sync_e:
                logger.error(f"同步应用增强功能也失败: {sync_e}")
    
    cls.__init__ = enhanced_init
    return cls


# 手动应用补丁的函数
def manually_apply_enhancements(xianyu_instance):
    """手动为已存在的XianyuLive实例应用增强功能"""
    try:
        SmartIntegrationPatch.apply_patches(xianyu_instance)
        logger.info(f"✅ 手动应用增强功能成功: {xianyu_instance.cookie_id}")
    except Exception as e:
        logger.error(f"❌ 手动应用增强功能失败: {e}")