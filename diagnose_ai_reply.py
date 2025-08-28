#!/usr/bin/env python3
"""
AI自动回复问题诊断脚本
"""

import asyncio
import os
import time
from pathlib import Path
from ai_reply_engine import ai_reply_engine
from db_manager import db_manager
from config import AUTO_REPLY

def check_log_files():
    """检查日志文件"""
    print("=== 日志文件检查 ===")
    logs_dir = Path('logs')
    
    if not logs_dir.exists():
        print("❌ logs目录不存在")
        return
    
    log_files = list(logs_dir.glob('*.log'))
    if not log_files:
        print("❌ 没有找到日志文件")
        return
    
    print(f"找到 {len(log_files)} 个日志文件:")
    for log_file in sorted(log_files):
        size = log_file.stat().st_size
        mtime = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(log_file.stat().st_mtime))
        print(f"  {log_file.name} ({size} bytes, 修改时间: {mtime})")
    
    # 检查最新的日志文件
    latest_log = max(log_files, key=lambda f: f.stat().st_mtime)
    print(f"\n最新日志文件: {latest_log.name}")
    
    try:
        with open(latest_log, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        if not lines:
            print("❌ 日志文件为空")
            return
            
        print(f"日志行数: {len(lines)}")
        
        # 查找消息相关日志
        message_lines = []
        for line in lines[-200:]:  # 检查最后200行
            if any(keyword in line for keyword in ['收到消息', '发出', 'AI回复', '关键词', '默认回复']):
                message_lines.append(line.strip())
        
        if message_lines:
            print(f"\n找到 {len(message_lines)} 条消息相关日志:")
            for line in message_lines[-10:]:  # 显示最后10条
                print(f"  {line}")
        else:
            print("\n❌ 没有找到消息相关日志")
            print("最后5行日志:")
            for line in lines[-5:]:
                print(f"  {line.strip()}")
                
    except Exception as e:
        print(f"❌ 读取日志文件失败: {e}")

def check_config():
    """检查配置"""
    print("\n=== 配置检查 ===")
    print(f"AUTO_REPLY.enabled: {AUTO_REPLY.get('enabled', False)}")
    print(f"AUTO_REPLY.api.enabled: {AUTO_REPLY.get('api', {}).get('enabled', False)}")
    
    # 检查AI设置
    settings = db_manager.get_all_ai_reply_settings()
    print(f"\nAI回复设置数量: {len(settings)}")
    for cookie_id, setting in settings.items():
        print(f"  {cookie_id}: AI启用={setting.get('ai_enabled', False)}")

def check_processes():
    """检查运行中的进程"""
    print("\n=== 进程检查 ===")
    try:
        import subprocess
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        lines = result.stdout.split('\n')
        
        xianyu_processes = []
        for line in lines:
            if 'xianyu' in line.lower() or 'Start.py' in line or 'XianyuAutoAsync.py' in line:
                xianyu_processes.append(line.strip())
        
        if xianyu_processes:
            print(f"找到 {len(xianyu_processes)} 个相关进程:")
            for proc in xianyu_processes:
                print(f"  {proc}")
        else:
            print("❌ 没有找到运行中的闲鱼相关进程")
            
    except Exception as e:
        print(f"❌ 检查进程失败: {e}")

async def test_ai_reply():
    """测试AI回复功能"""
    print("\n=== AI回复功能测试 ===")
    
    cookie_id = "尔选本地生活"
    test_message = "这个多少钱？"
    
    # 检查AI是否启用
    is_enabled = ai_reply_engine.is_ai_enabled(cookie_id)
    print(f"AI回复启用状态: {is_enabled}")
    
    if not is_enabled:
        print("❌ AI回复未启用")
        return
    
    # 测试生成回复
    try:
        item_info = {
            'title': '测试餐饮券',
            'price': 25.8,
            'desc': '测试商品描述'
        }
        
        reply = ai_reply_engine.generate_reply(
            message=test_message,
            item_info=item_info,
            chat_id="test_chat",
            cookie_id=cookie_id,
            user_id="test_user",
            item_id="test_item"
        )
        
        if reply:
            print(f"✅ AI回复测试成功: {reply}")
        else:
            print("❌ AI回复测试失败，返回None")
            
    except Exception as e:
        print(f"❌ AI回复测试异常: {e}")
        import traceback
        traceback.print_exc()

def main():
    """主函数"""
    print("🔍 AI自动回复问题诊断")
    print("=" * 50)
    
    check_log_files()
    check_config()
    check_processes()
    
    # 运行异步测试
    asyncio.run(test_ai_reply())
    
    print("\n" + "=" * 50)
    print("📋 诊断建议:")
    print("1. 如果没有找到运行中的进程，请启动主程序: python3 Start.py")
    print("2. 如果没有消息日志，检查WebSocket连接是否正常")
    print("3. 如果AI回复测试失败，检查API密钥和网络连接")
    print("4. 确保账号已登录且WebSocket连接正常")

if __name__ == "__main__":
    main()