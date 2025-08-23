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
        self._init_default_prompts()
    
    def _init_default_prompts(self):
        """从prompts文件夹初始化默认提示词"""
        self.default_prompts = {}
        prompts_dir = Path(__file__).parent / "prompts"
        
        # 定义提示词文件映射
        prompt_files = {
            'classify': 'classify_prompt.txt',
            'price': 'price_prompt.txt', 
            'tech': 'tech_prompt.txt',
            'default': 'default_prompt.txt'
        }
        
        # 从文件读取提示词
        for prompt_type, filename in prompt_files.items():
            file_path = prompts_dir / filename
            try:
                if file_path.exists():
                    with open(file_path, 'r', encoding='utf-8') as f:
                        self.default_prompts[prompt_type] = f.read().strip()
                    logger.info(f"成功加载提示词文件: {filename}")
                else:
                    logger.warning(f"提示词文件不存在: {file_path}")
                    # 设置一个基本的fallback提示词
                    self.default_prompts[prompt_type] = self._get_fallback_prompt(prompt_type)
            except Exception as e:
                logger.error(f"读取提示词文件失败 {filename}: {e}")
                # 设置一个基本的fallback提示词
                self.default_prompts[prompt_type] = self._get_fallback_prompt(prompt_type)
                
        logger.info(f"提示词初始化完成，加载了 {len(self.default_prompts)} 个提示词")
    
    def _get_fallback_prompt(self, prompt_type: str) -> str:
        """获取fallback提示词"""
        fallback_prompts = {
            'classify': '你是意图分类专家，判断用户消息类型，返回price/tech/default之一。',
            'price': '你是专业电商卖家，坚持价格不议价。语言简短，每句≤10字，总字数≤40字。',
            'tech': '你是技术专家，用通俗语言解答产品问题。每句≤10字，总字数≤40字。',
            'default': '你是电商卖家，提供专业客服。语言简短，每句≤10字，总字数≤40字。'
        }
        return fallback_prompts.get(prompt_type, '请提供专业的客服回复。')
    
    def get_client(self, cookie_id: str) -> Optional[OpenAI]:
        """获取指定账号的OpenAI客户端"""
        if cookie_id not in self.clients:
            settings = db_manager.get_ai_reply_settings(cookie_id)
            if not settings['ai_enabled'] or not settings['api_key']:
                return None
            
            try:
                logger.info(f"创建OpenAI客户端 {cookie_id}: base_url={settings['base_url']}, api_key={'***' + settings['api_key'][-4:] if settings['api_key'] else 'None'}")
                self.clients[cookie_id] = OpenAI(
                    api_key=settings['api_key'],
                    base_url=settings['base_url']
                )
                logger.info(f"为账号 {cookie_id} 创建OpenAI客户端成功，实际base_url: {self.clients[cookie_id].base_url}")
            except Exception as e:
                logger.error(f"创建OpenAI客户端失败 {cookie_id}: {e}")
                return None
        
        return self.clients[cookie_id]

    def _is_dashscope_api(self, settings: dict) -> bool:
        """判断是否为DashScope API - 只有选择自定义模型时才使用"""
        model_name = settings.get('model_name', '')
        base_url = settings.get('base_url', '')

        # 只有当模型名称为"custom"或"自定义"时，才使用DashScope API格式
        # 其他情况都使用OpenAI兼容格式
        is_custom_model = model_name.lower() in ['custom', '自定义', 'dashscope', 'qwen-custom']
        is_dashscope_url = 'dashscope.aliyuncs.com' in base_url

        logger.info(f"API类型判断: model_name={model_name}, is_custom_model={is_custom_model}, is_dashscope_url={is_dashscope_url}")

        return is_custom_model and is_dashscope_url

    def _call_dashscope_api(self, settings: dict, messages: list, max_tokens: int = 100, temperature: float = 0.7) -> str:
        """调用DashScope API"""
        # 提取app_id从base_url
        base_url = settings['base_url']
        if '/apps/' in base_url:
            app_id = base_url.split('/apps/')[-1].split('/')[0]
        else:
            raise ValueError("DashScope API URL中未找到app_id")

        # 构建请求URL
        url = f"https://dashscope.aliyuncs.com/api/v1/apps/{app_id}/completion"

        # 构建提示词（将messages合并为单个prompt）
        system_content = ""
        user_content = ""

        for msg in messages:
            if msg['role'] == 'system':
                system_content = msg['content']
            elif msg['role'] == 'user':
                user_content = msg['content']

        # 构建更清晰的prompt格式
        if system_content and user_content:
            prompt = f"{system_content}\n\n用户问题：{user_content}\n\n请直接回答用户的问题："
        elif user_content:
            prompt = user_content
        else:
            prompt = "\n".join([f"{msg['role']}: {msg['content']}" for msg in messages])

        # 构建请求数据
        data = {
            "input": {
                "prompt": prompt
            },
            "parameters": {
                "max_tokens": max_tokens,
                "temperature": temperature
            },
            "debug": {}
        }

        headers = {
            "Authorization": f"Bearer {settings['api_key']}",
            "Content-Type": "application/json"
        }

        logger.info(f"DashScope API请求: {url}")
        logger.info(f"发送的prompt: {prompt}")
        logger.debug(f"请求数据: {json.dumps(data, ensure_ascii=False)}")

        response = requests.post(url, headers=headers, json=data, timeout=30)

        if response.status_code != 200:
            logger.error(f"DashScope API请求失败: {response.status_code} - {response.text}")
            raise Exception(f"DashScope API请求失败: {response.status_code} - {response.text}")

        result = response.json()
        logger.debug(f"DashScope API响应: {json.dumps(result, ensure_ascii=False)}")

        # 提取回复内容
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

    def is_ai_enabled(self, cookie_id: str) -> bool:
        """检查指定账号是否启用AI回复"""
        settings = db_manager.get_ai_reply_settings(cookie_id)
        return settings['ai_enabled']
    
    def detect_intent(self, message: str, cookie_id: str) -> str:
        """检测用户消息意图"""
        try:
            settings = db_manager.get_ai_reply_settings(cookie_id)
            if not settings['ai_enabled'] or not settings['api_key']:
                return 'default'

            custom_prompts = json.loads(settings['custom_prompts']) if settings['custom_prompts'] else {}
            classify_prompt = custom_prompts.get('classify', self.default_prompts['classify'])

            # 打印调试信息
            logger.info(f"AI设置调试 {cookie_id}: base_url={settings['base_url']}, model={settings['model_name']}")

            messages = [
                {"role": "system", "content": classify_prompt},
                {"role": "user", "content": message}
            ]

            # 根据API类型选择调用方式
            if self._is_dashscope_api(settings):
                logger.info(f"使用DashScope API进行意图检测")
                response_text = self._call_dashscope_api(settings, messages, max_tokens=10, temperature=0.1)
            else:
                logger.info(f"使用OpenAI兼容API进行意图检测")
                client = self.get_client(cookie_id)
                if not client:
                    return 'default'
                logger.info(f"OpenAI客户端base_url: {client.base_url}")
                response_text = self._call_openai_api(client, settings, messages, max_tokens=10, temperature=0.1)

            intent = response_text.lower()
            if intent in ['price', 'tech', 'default']:
                return intent
            else:
                return 'default'

        except Exception as e:
            logger.error(f"意图检测失败 {cookie_id}: {e}")
            # 打印更详细的错误信息
            if hasattr(e, 'response') and hasattr(e.response, 'url'):
                logger.error(f"请求URL: {e.response.url}")
            if hasattr(e, 'request') and hasattr(e.request, 'url'):
                logger.error(f"请求URL: {e.request.url}")
            return 'default'
    
    def generate_reply(self, message: str, item_info: dict, chat_id: str,
                      cookie_id: str, user_id: str, item_id: str) -> Optional[str]:
        """生成AI回复"""
        if not self.is_ai_enabled(cookie_id):
            return None
        
        try:
            # 1. 获取AI回复设置
            settings = db_manager.get_ai_reply_settings(cookie_id)

            # 2. 检测意图
            intent = self.detect_intent(message, cookie_id)
            logger.info(f"检测到意图: {intent} (账号: {cookie_id})")

            # 3. 获取对话历史
            context = self.get_conversation_context(chat_id, cookie_id)

            # 4. 获取议价次数
            bargain_count = self.get_bargain_count(chat_id, cookie_id)

            # 5. 检查议价轮数限制
            if intent == "price":
                max_bargain_rounds = settings.get('max_bargain_rounds', 3)
                if bargain_count >= max_bargain_rounds:
                    logger.info(f"议价次数已达上限 ({bargain_count}/{max_bargain_rounds})，拒绝继续议价")
                    # 返回拒绝议价的回复
                    refuse_reply = f"抱歉，这个价格已经是最优惠的了，不能再便宜了哦！"
                    # 保存对话记录
                    self.save_conversation(chat_id, cookie_id, user_id, item_id, "user", message, intent)
                    self.save_conversation(chat_id, cookie_id, user_id, item_id, "assistant", refuse_reply, intent)
                    return refuse_reply

            # 6. 构建提示词
            custom_prompts = json.loads(settings['custom_prompts']) if settings['custom_prompts'] else {}
            system_prompt = custom_prompts.get(intent, self.default_prompts[intent])

            # 7. 构建商品信息
            item_desc = f"商品标题: {item_info.get('title', '未知')}\n"
            item_desc += f"商品价格: {item_info.get('price', '未知')}元\n"
            item_desc += f"商品描述: {item_info.get('desc', '无')}"

            # 8. 构建对话历史
            context_str = "\n".join([f"{msg['role']}: {msg['content']}" for msg in context[-10:]])  # 最近10条

            # 9. 构建用户消息
            max_bargain_rounds = settings.get('max_bargain_rounds', 3)
            max_discount_percent = settings.get('max_discount_percent', 10)
            max_discount_amount = settings.get('max_discount_amount', 100)

            user_prompt = f"""商品信息：
{item_desc}

对话历史：
{context_str}

议价设置：
- 当前议价次数：{bargain_count}
- 最大议价轮数：{max_bargain_rounds}
- 最大优惠百分比：{max_discount_percent}%
- 最大优惠金额：{max_discount_amount}元

用户消息：{message}

请根据以上信息生成回复："""

            # 10. 调用AI生成回复
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]

            # 根据API类型选择调用方式
            if self._is_dashscope_api(settings):
                logger.info(f"使用DashScope API生成回复")
                reply = self._call_dashscope_api(settings, messages, max_tokens=100, temperature=0.7)
            else:
                logger.info(f"使用OpenAI兼容API生成回复")
                client = self.get_client(cookie_id)
                if not client:
                    return None
                reply = self._call_openai_api(client, settings, messages, max_tokens=100, temperature=0.7)

            # 11. 保存对话记录
            self.save_conversation(chat_id, cookie_id, user_id, item_id, "user", message, intent)
            self.save_conversation(chat_id, cookie_id, user_id, item_id, "assistant", reply, intent)

            # 12. 更新议价次数
            if intent == "price":
                self.increment_bargain_count(chat_id, cookie_id)
            
            logger.info(f"AI回复生成成功 (账号: {cookie_id}): {reply}")
            return reply
            
        except Exception as e:
            logger.error(f"AI回复生成失败 {cookie_id}: {e}")
            # 打印更详细的错误信息
            if hasattr(e, 'response') and hasattr(e.response, 'url'):
                logger.error(f"请求URL: {e.response.url}")
            if hasattr(e, 'request') and hasattr(e.request, 'url'):
                logger.error(f"请求URL: {e.request.url}")
            return None
    
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
                # 反转顺序，使其按时间正序
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
    
    def get_bargain_count(self, chat_id: str, cookie_id: str) -> int:
        """获取议价次数"""
        try:
            with db_manager.lock:
                cursor = db_manager.conn.cursor()
                cursor.execute('''
                SELECT COUNT(*) FROM ai_conversations 
                WHERE chat_id = ? AND cookie_id = ? AND intent = 'price' AND role = 'user'
                ''', (chat_id, cookie_id))
                
                result = cursor.fetchone()
                return result[0] if result else 0
        except Exception as e:
            logger.error(f"获取议价次数失败: {e}")
            return 0
    
    def increment_bargain_count(self, chat_id: str, cookie_id: str):
        """增加议价次数（通过保存记录自动增加）"""
        # 议价次数通过查询price意图的用户消息数量来计算，无需单独操作
        pass
    
    def clear_client_cache(self, cookie_id: str = None):
        """清理客户端缓存"""
        if cookie_id:
            self.clients.pop(cookie_id, None)
            logger.info(f"清理账号 {cookie_id} 的客户端缓存")
        else:
            self.clients.clear()
            logger.info("清理所有客户端缓存")


# 全局AI回复引擎实例
ai_reply_engine = AIReplyEngine()
