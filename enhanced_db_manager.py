#!/usr/bin/env python3
"""
增强数据库管理器
扩展现有数据库以支持更丰富的商品信息存储和对话上下文管理
不修改原有表结构，采用扩展表的方式
"""

import sqlite3
import json
import time
from typing import Dict, List, Optional, Any
from loguru import logger
from db_manager import db_manager


class EnhancedDBManager:
    """增强数据库管理器 - 扩展现有功能"""
    
    def __init__(self):
        self.db_manager = db_manager  # 使用现有的数据库管理器
        self.init_enhanced_tables()
    
    def init_enhanced_tables(self):
        """初始化增强功能所需的新表结构"""
        try:
            with self.db_manager.lock:
                cursor = self.db_manager.conn.cursor()
                
                # 创建增强商品信息表
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS enhanced_item_info (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cookie_id TEXT NOT NULL,
                    item_id TEXT NOT NULL,
                    
                    -- 扩展的商品信息字段
                    seller_name TEXT DEFAULT '',
                    category_name TEXT DEFAULT '',
                    area TEXT DEFAULT '',
                    status TEXT DEFAULT '',
                    main_image TEXT DEFAULT '',
                    
                    -- 商品属性和标签（JSON格式存储）
                    attributes TEXT DEFAULT '[]',  -- JSON数组
                    tags TEXT DEFAULT '[]',        -- JSON数组
                    images TEXT DEFAULT '[]',      -- JSON数组
                    
                    -- 完整API响应数据
                    raw_api_data TEXT DEFAULT '{}',  -- 完整的API返回JSON
                    
                    -- 缓存管理
                    cache_timestamp REAL NOT NULL,  -- 缓存时间戳
                    is_enhanced BOOLEAN DEFAULT TRUE,
                    
                    -- 时间戳
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    -- 约束
                    UNIQUE(cookie_id, item_id),
                    FOREIGN KEY (cookie_id) REFERENCES cookies(id) ON DELETE CASCADE
                )
                ''')
                
                # 创建对话上下文管理表
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS conversation_context (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id TEXT NOT NULL,
                    cookie_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    item_id TEXT DEFAULT '',
                    
                    -- 对话历史（JSON格式）
                    message_history TEXT DEFAULT '[]',  -- 消息历史数组
                    
                    -- 对话统计
                    negotiation_count INTEGER DEFAULT 0,  -- 议价次数
                    total_messages INTEGER DEFAULT 0,     -- 总消息数
                    
                    -- 对话状态
                    last_intent TEXT DEFAULT 'general',   -- 最后检测到的意图
                    conversation_stage TEXT DEFAULT 'initial',  -- 对话阶段
                    
                    -- 时间戳
                    last_update REAL NOT NULL,  -- 最后更新时间戳
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    -- 约束
                    UNIQUE(chat_id),
                    FOREIGN KEY (cookie_id) REFERENCES cookies(id) ON DELETE CASCADE
                )
                ''')
                
                # 创建AI回复缓存表
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS ai_reply_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cache_key TEXT NOT NULL UNIQUE,
                    
                    -- 缓存内容
                    user_message TEXT NOT NULL,
                    ai_reply TEXT NOT NULL,
                    
                    -- 上下文信息
                    cookie_id TEXT NOT NULL,
                    item_id TEXT DEFAULT '',
                    intent TEXT DEFAULT 'general',
                    
                    -- 缓存管理
                    cache_timestamp REAL NOT NULL,
                    expire_time REAL NOT NULL,
                    
                    -- 时间戳
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    FOREIGN KEY (cookie_id) REFERENCES cookies(id) ON DELETE CASCADE
                )
                ''')
                
                # 创建索引以提高查询性能
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_enhanced_item_cookie_item ON enhanced_item_info(cookie_id, item_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_enhanced_item_cache_time ON enhanced_item_info(cache_timestamp)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_conversation_chat_id ON conversation_context(chat_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_conversation_last_update ON conversation_context(last_update)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_ai_cache_key ON ai_reply_cache(cache_key)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_ai_cache_expire ON ai_reply_cache(expire_time)')
                
                self.db_manager.conn.commit()
                logger.info("增强数据库表结构初始化完成")
                
        except Exception as e:
            logger.error(f"初始化增强数据库表失败: {e}")
            if self.db_manager.conn:
                self.db_manager.conn.rollback()
    
    def save_enhanced_item_info(self, cookie_id: str, item_id: str, enhanced_info: Dict) -> bool:
        """保存增强商品信息"""
        try:
            with self.db_manager.lock:
                cursor = self.db_manager.conn.cursor()
                
                # 准备数据
                seller_name = enhanced_info.get('seller_name', '')
                category_name = enhanced_info.get('category', '')
                area = enhanced_info.get('area', '')
                status = enhanced_info.get('status', '')
                main_image = enhanced_info.get('main_image', '')
                
                # 序列化JSON字段
                attributes = json.dumps(enhanced_info.get('attributes', []), ensure_ascii=False)
                tags = json.dumps(enhanced_info.get('tags', []), ensure_ascii=False)
                images = json.dumps(enhanced_info.get('images', []), ensure_ascii=False)
                raw_api_data = json.dumps(enhanced_info.get('raw_data', {}), ensure_ascii=False)
                
                cache_timestamp = enhanced_info.get('updated_at', time.time())
                
                # 使用 REPLACE 语法进行插入或更新
                cursor.execute('''
                REPLACE INTO enhanced_item_info (
                    cookie_id, item_id, seller_name, category_name, area, status, main_image,
                    attributes, tags, images, raw_api_data, cache_timestamp, is_enhanced,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ''', (
                    cookie_id, item_id, seller_name, category_name, area, status, main_image,
                    attributes, tags, images, raw_api_data, cache_timestamp, True
                ))
                
                self.db_manager.conn.commit()
                logger.debug(f"增强商品信息已保存: {item_id}")
                return True
                
        except Exception as e:
            logger.error(f"保存增强商品信息失败: {e}")
            if self.db_manager.conn:
                self.db_manager.conn.rollback()
            return False
    
    def get_enhanced_item_info(self, cookie_id: str, item_id: str) -> Optional[Dict]:
        """获取增强商品信息"""
        try:
            with self.db_manager.lock:
                cursor = self.db_manager.conn.cursor()
                
                # 先尝试获取增强信息
                cursor.execute('''
                SELECT 
                    seller_name, category_name, area, status, main_image,
                    attributes, tags, images, raw_api_data, cache_timestamp, is_enhanced
                FROM enhanced_item_info 
                WHERE cookie_id = ? AND item_id = ?
                ''', (cookie_id, item_id))
                
                enhanced_row = cursor.fetchone()
                
                # 获取基础商品信息
                basic_info = self.db_manager.get_item_info(cookie_id, item_id)
                
                if enhanced_row:
                    # 合并增强信息和基础信息
                    try:
                        attributes = json.loads(enhanced_row[5]) if enhanced_row[5] else []
                    except:
                        attributes = []
                    
                    try:
                        tags = json.loads(enhanced_row[6]) if enhanced_row[6] else []
                    except:
                        tags = []
                    
                    try:
                        images = json.loads(enhanced_row[7]) if enhanced_row[7] else []
                    except:
                        images = []
                    
                    try:
                        raw_data = json.loads(enhanced_row[8]) if enhanced_row[8] else {}
                    except:
                        raw_data = {}
                    
                    enhanced_info = {
                        # 基础信息
                        'title': basic_info.get('item_title', '') if basic_info else enhanced_row[0] or '',
                        'price': basic_info.get('item_price', '') if basic_info else '面议',
                        'description': basic_info.get('item_description', '') if basic_info else '',
                        
                        # 增强信息
                        'seller_name': enhanced_row[0] or '',
                        'category': enhanced_row[1] or '',
                        'area': enhanced_row[2] or '',
                        'status': enhanced_row[3] or '',
                        'main_image': enhanced_row[4] or '',
                        'attributes': attributes,
                        'tags': tags,
                        'images': images,
                        'raw_data': raw_data,
                        'enhanced': True,
                        'updated_at': enhanced_row[9]
                    }
                    
                    return enhanced_info
                
                elif basic_info:
                    # 只有基础信息，构建基本的增强格式
                    return {
                        'title': basic_info.get('item_title', ''),
                        'price': basic_info.get('item_price', ''),
                        'description': basic_info.get('item_description', ''),
                        'seller_name': '',
                        'category': '',
                        'area': '',
                        'status': '',
                        'main_image': '',
                        'attributes': [],
                        'tags': [],
                        'images': [],
                        'raw_data': {},
                        'enhanced': False,
                        'updated_at': time.time()
                    }
                
                return None
                
        except Exception as e:
            logger.error(f"获取增强商品信息失败: {e}")
            return None
    
    def save_conversation_context(self, chat_id: str, cookie_id: str, user_id: str, 
                                 item_id: str = '', message_history: List = None,
                                 negotiation_count: int = 0, last_intent: str = 'general') -> bool:
        """保存对话上下文"""
        try:
            if message_history is None:
                message_history = []
            
            with self.db_manager.lock:
                cursor = self.db_manager.conn.cursor()
                
                message_history_json = json.dumps(message_history, ensure_ascii=False)
                current_time = time.time()
                total_messages = len(message_history)
                
                cursor.execute('''
                REPLACE INTO conversation_context (
                    chat_id, cookie_id, user_id, item_id, message_history,
                    negotiation_count, total_messages, last_intent,
                    conversation_stage, last_update
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    chat_id, cookie_id, user_id, item_id, message_history_json,
                    negotiation_count, total_messages, last_intent,
                    'ongoing', current_time
                ))
                
                self.db_manager.conn.commit()
                logger.debug(f"对话上下文已保存: {chat_id}")
                return True
                
        except Exception as e:
            logger.error(f"保存对话上下文失败: {e}")
            if self.db_manager.conn:
                self.db_manager.conn.rollback()
            return False
    
    def get_conversation_context(self, chat_id: str, expire_time: int = 3600) -> Optional[Dict]:
        """获取对话上下文"""
        try:
            with self.db_manager.lock:
                cursor = self.db_manager.conn.cursor()
                
                cursor.execute('''
                SELECT 
                    cookie_id, user_id, item_id, message_history,
                    negotiation_count, total_messages, last_intent,
                    conversation_stage, last_update
                FROM conversation_context 
                WHERE chat_id = ?
                ''', (chat_id,))
                
                row = cursor.fetchone()
                
                if row:
                    current_time = time.time()
                    last_update = row[8]
                    
                    # 检查是否过期
                    if current_time - last_update > expire_time:
                        # 删除过期的上下文
                        cursor.execute('DELETE FROM conversation_context WHERE chat_id = ?', (chat_id,))
                        self.db_manager.conn.commit()
                        logger.debug(f"对话上下文已过期并清理: {chat_id}")
                        return None
                    
                    try:
                        message_history = json.loads(row[3]) if row[3] else []
                    except:
                        message_history = []
                    
                    return {
                        'cookie_id': row[0],
                        'user_id': row[1],
                        'item_id': row[2],
                        'message_history': message_history,
                        'negotiation_count': row[4],
                        'total_messages': row[5],
                        'last_intent': row[6],
                        'conversation_stage': row[7],
                        'last_update': last_update
                    }
                
                return None
                
        except Exception as e:
            logger.error(f"获取对话上下文失败: {e}")
            return None
    
    def add_message_to_context(self, chat_id: str, role: str, content: str, 
                              intent: str = 'general', max_messages: int = 10) -> bool:
        """向对话上下文添加消息"""
        try:
            # 获取现有上下文
            context = self.get_conversation_context(chat_id)
            
            if context:
                message_history = context['message_history']
                negotiation_count = context['negotiation_count']
                
                # 检测议价
                if role == 'user' and intent == 'price':
                    negotiation_count += 1
                
                # 添加新消息
                message_history.append({
                    'role': role,
                    'content': content,
                    'timestamp': time.time(),
                    'intent': intent
                })
                
                # 限制消息数量
                if len(message_history) > max_messages:
                    message_history = message_history[-max_messages:]
                
                # 更新上下文
                return self.save_conversation_context(
                    chat_id=chat_id,
                    cookie_id=context['cookie_id'],
                    user_id=context['user_id'],
                    item_id=context['item_id'],
                    message_history=message_history,
                    negotiation_count=negotiation_count,
                    last_intent=intent
                )
            
            return False
            
        except Exception as e:
            logger.error(f"添加消息到上下文失败: {e}")
            return False
    
    def cleanup_expired_data(self, item_cache_expire: int = 86400, 
                           context_expire: int = 3600, reply_cache_expire: int = 300) -> Dict[str, int]:
        """清理过期数据"""
        try:
            current_time = time.time()
            cleanup_stats = {'items': 0, 'contexts': 0, 'replies': 0}
            
            with self.db_manager.lock:
                cursor = self.db_manager.conn.cursor()
                
                # 清理过期的商品信息缓存
                cursor.execute('''
                DELETE FROM enhanced_item_info 
                WHERE cache_timestamp < ?
                ''', (current_time - item_cache_expire,))
                cleanup_stats['items'] = cursor.rowcount
                
                # 清理过期的对话上下文
                cursor.execute('''
                DELETE FROM conversation_context 
                WHERE last_update < ?
                ''', (current_time - context_expire,))
                cleanup_stats['contexts'] = cursor.rowcount
                
                # 清理过期的回复缓存
                cursor.execute('''
                DELETE FROM ai_reply_cache 
                WHERE expire_time < ?
                ''', (current_time,))
                cleanup_stats['replies'] = cursor.rowcount
                
                self.db_manager.conn.commit()
                
                if sum(cleanup_stats.values()) > 0:
                    logger.info(f"数据清理完成: 商品{cleanup_stats['items']}条, 对话{cleanup_stats['contexts']}条, 回复{cleanup_stats['replies']}条")
                
                return cleanup_stats
                
        except Exception as e:
            logger.error(f"清理过期数据失败: {e}")
            if self.db_manager.conn:
                self.db_manager.conn.rollback()
            return {'items': 0, 'contexts': 0, 'replies': 0}
    
    def get_negotiation_count(self, chat_id: str) -> int:
        """获取议价次数"""
        try:
            context = self.get_conversation_context(chat_id)
            if context:
                return context.get('negotiation_count', 0)
            return 0
        except Exception as e:
            logger.error(f"获取议价次数失败: {e}")
            return 0


# 全局增强数据库管理器实例
enhanced_db_manager = EnhancedDBManager()