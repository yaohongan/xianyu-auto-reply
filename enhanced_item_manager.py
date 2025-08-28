#!/usr/bin/env python3
"""
增强的商品信息管理器
参考XianyuAutoAgent的实现，优化商品信息获取和缓存策略
"""

import asyncio
import json
import time
from typing import Dict, Any, Optional
from loguru import logger
from enhanced_db_manager import enhanced_db_manager


class EnhancedItemManager:
    """增强的商品信息管理器"""
    
    def __init__(self):
        # 商品信息缓存（内存）- 24小时有效
        self._item_cache = {}  # {item_id: {'info': dict, 'timestamp': float, 'full_detail': dict}}
        self._cache_lock = asyncio.Lock()
        self.cache_duration = 24 * 60 * 60  # 24小时
    
    async def get_enhanced_item_info(self, cookie_id: str, item_id: str, xianyu_instance) -> Dict[str, Any]:
        """
        获取增强的商品信息
        
        优先级：内存缓存 > 数据库 > 实时API获取
        
        Args:
            cookie_id: Cookie ID
            item_id: 商品ID
            xianyu_instance: XianyuLive实例，用于API调用
            
        Returns:
            增强的商品信息字典
        """
        try:
            # 1. 检查内存缓存
            async with self._cache_lock:
                if item_id in self._item_cache:
                    cached = self._item_cache[item_id]
                    if time.time() - cached['timestamp'] < self.cache_duration:
                        logger.debug(f"从内存缓存获取商品信息: {item_id}")
                        return cached['info']
                    else:
                        # 清除过期缓存
                        del self._item_cache[item_id]
            
            # 2. 检查增强数据库
            db_item = enhanced_db_manager.get_enhanced_item_info(cookie_id, item_id)
            
            # 3. 如果数据库有完整信息且较新，直接使用
            if db_item and db_item.get('enhanced') and db_item.get('updated_at'):
                try:
                    updated_time = float(db_item.get('updated_at', 0))
                    if time.time() - updated_time < self.cache_duration:
                        await self._cache_item_info(item_id, db_item)
                        logger.debug(f"从增强数据库获取商品信息: {item_id}")
                        return db_item
                except Exception as e:
                    logger.warning(f"解析增强数据库商品信息时间戳失败: {e}")
            
            # 4. 实时获取完整商品信息
            logger.info(f"实时获取商品信息: {item_id}")
            api_result = await xianyu_instance.get_item_info(item_id)
            
            if api_result and 'data' in api_result:
                # 解析完整的API返回数据
                enhanced_info = await self._parse_api_response(api_result)
                
                # 保存到数据库
                await self._save_enhanced_info_to_db(cookie_id, item_id, api_result, enhanced_info)
                
                # 缓存到内存
                await self._cache_item_info(item_id, enhanced_info)
                
                logger.info(f"API获取商品信息成功: {enhanced_info.get('title', 'Unknown')}")
                return enhanced_info
            else:
                # API失败，使用数据库的基础信息或默认信息
                if db_item:
                    logger.warning(f"API失败，使用数据库信息: {item_id}")
                    return db_item
                else:
                    # 返回默认信息
                    default_info = await self._get_default_item_info(item_id)
                    logger.warning(f"商品信息获取失败，使用默认信息: {item_id}")
                    return default_info
                    
        except Exception as e:
            logger.error(f"获取增强商品信息失败: {e}")
            return await self._get_default_item_info(item_id)
    
    async def _parse_api_response(self, api_result: Dict) -> Dict[str, Any]:
        """解析API返回的完整商品信息"""
        try:
            data = api_result.get('data', {})
            item_data = data.get('itemDO', {})
            share_data = item_data.get('shareData', {})
            
            # 基础信息
            title = item_data.get('title', '未知商品')
            price = item_data.get('price', '面议')
            
            # 解析shareInfoJsonString获取详细描述
            description = '暂无描述'
            try:
                share_info = share_data.get('shareInfoJsonString', '')
                if share_info:
                    share_json = json.loads(share_info)
                    description = share_json.get('content', description)
            except:
                pass
            
            # 商品属性和标签
            attributes = item_data.get('attributes', [])
            tags = item_data.get('tags', [])
            
            # 分类信息
            category = item_data.get('category', {})
            category_name = category.get('name', '未知分类')
            
            # 卖家信息
            seller = item_data.get('seller', {})
            seller_name = seller.get('nick', '匿名卖家')
            
            # 商品状态
            status = item_data.get('status', {})
            item_status = status.get('name', '未知状态')
            
            # 图片信息
            images = item_data.get('images', [])
            main_image = images[0] if images else ''
            
            # 地理位置
            location = item_data.get('location', {})
            area = location.get('name', '位置未知')
            
            # 构建增强信息
            enhanced_info = {
                # 基础信息
                'title': title,
                'price': self._normalize_price(price),
                'description': description,
                'main_image': main_image,
                'area': area,
                
                # 扩展信息
                'attributes': attributes,
                'tags': [tag.get('name', '') for tag in tags if isinstance(tag, dict)],
                'category': category_name,
                'seller_name': seller_name,
                'status': item_status,
                'images': images,
                
                # 完整的原始数据
                'raw_data': api_result,
                'enhanced': True,
                'updated_at': time.time()
            }
            
            return enhanced_info
            
        except Exception as e:
            logger.error(f"解析API响应失败: {e}")
            return await self._get_default_item_info('')
    
    
    async def _save_enhanced_info_to_db(self, cookie_id: str, item_id: str, 
                                       api_result: Dict, enhanced_info: Dict):
        """保存增强信息到数据库"""
        try:
            # 先保存到基础表（保持兼容性）
            from db_manager import db_manager
            detail_json = json.dumps(api_result, ensure_ascii=False)
            
            db_manager.save_item_info(
                cookie_id=cookie_id,
                item_id=item_id,
                item_data=detail_json
            )
            
            # 保存到增强表
            success = enhanced_db_manager.save_enhanced_item_info(
                cookie_id=cookie_id,
                item_id=item_id,
                enhanced_info=enhanced_info
            )
            
            if success:
                logger.debug(f"增强商品信息已保存到数据库: {item_id}")
            
        except Exception as e:
            logger.error(f"保存增强信息到数据库失败: {e}")
    
    async def _cache_item_info(self, item_id: str, enhanced_info: Dict):
        """缓存商品信息到内存"""
        try:
            async with self._cache_lock:
                self._item_cache[item_id] = {
                    'info': enhanced_info,
                    'timestamp': time.time()
                }
                
                # 清理过期缓存
                current_time = time.time()
                expired_keys = [
                    key for key, value in self._item_cache.items()
                    if current_time - value['timestamp'] > self.cache_duration
                ]
                for key in expired_keys:
                    del self._item_cache[key]
                    
        except Exception as e:
            logger.error(f"缓存商品信息失败: {e}")
    
    async def _get_default_item_info(self, item_id: str) -> Dict[str, Any]:
        """获取默认商品信息"""
        return {
            'title': '餐饮券商品',
            'price': '面议',
            'description': '详细信息请查看商品详情页',
            'main_image': '',
            'area': '位置未知',
            'attributes': [],
            'tags': [],
            'category': '餐饮券',
            'seller_name': '匿名卖家',
            'status': '在售',
            'images': [],
            'raw_data': {},
            'enhanced': False,
            'updated_at': time.time()
        }
    
    def _normalize_price(self, price) -> str:
        """标准化价格格式"""
        if not price:
            return '面议'
        
        price_str = str(price).strip()
        if not price_str or price_str == '0':
            return '面议'
            
        # 确保价格有¥符号
        if not price_str.startswith('¥') and price_str.replace('.', '').isdigit():
            return f'¥{price_str}'
        
        return price_str


# 全局增强商品信息管理器实例
enhanced_item_manager = EnhancedItemManager()