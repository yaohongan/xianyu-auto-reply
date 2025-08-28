#!/usr/bin/env python3
"""
WebSocket消息结构调试脚本
"""

import json
import re
from pathlib import Path

def analyze_websocket_messages():
    """分析WebSocket消息日志"""
    print("=== WebSocket消息结构分析 ===")
    
    log_file = Path('logs/xianyu_2025-08-25.log')
    if not log_file.exists():
        print("❌ 日志文件不存在")
        return
    
    with open(log_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # 查找WebSocket消息
    message_logs = []
    for i, line in enumerate(lines):
        if '收到WebSocket消息:' in line and '字节' in line:
            try:
                # 提取消息大小
                size_part = line.split('收到WebSocket消息:')[1].split('字节')[0].strip()
                size = int(size_part)
                timestamp = line.split('|')[0].strip()
                
                message_logs.append({
                    'timestamp': timestamp,
                    'size': size,
                    'line_index': i
                })
            except:
                continue
    
    print(f"找到 {len(message_logs)} 条WebSocket消息:")
    for msg in message_logs[-10:]:  # 显示最后10条
        print(f"  {msg['timestamp']} - {msg['size']} 字节")
    
    # 分析消息大小分布
    sizes = [msg['size'] for msg in message_logs]
    if sizes:
        print(f"\n消息大小统计:")
        print(f"  最小: {min(sizes)} 字节")
        print(f"  最大: {max(sizes)} 字节") 
        print(f"  平均: {sum(sizes)//len(sizes)} 字节")
        
        # 按大小分类
        size_groups = {}
        for size in sizes:
            if size < 100:
                group = "小消息(<100字节)"
            elif size < 1000:
                group = "中等消息(100-1000字节)"
            else:
                group = "大消息(>1000字节)"
            
            size_groups[group] = size_groups.get(group, 0) + 1
        
        print("\n消息大小分布:")
        for group, count in size_groups.items():
            print(f"  {group}: {count} 条")
    
    # 查找是否有真正的聊天消息迹象
    chat_keywords = ['send_user_name', 'send_message', 'content', 'msg', 'text']
    potential_chat_lines = []
    
    for line in lines[-200:]:  # 检查最后200行
        line_lower = line.lower()
        if any(keyword in line_lower for keyword in chat_keywords):
            if '收到' in line or '处理' in line or 'AI' in line:
                potential_chat_lines.append(line.strip())
    
    if potential_chat_lines:
        print(f"\n🔍 可能的聊天相关日志 ({len(potential_chat_lines)} 条):")
        for line in potential_chat_lines[-5:]:  # 显示最后5条
            print(f"  {line}")
    else:
        print("\n❌ 没有发现聊天相关的日志")
    
    # 检查非同步包消息的日志
    non_sync_messages = []
    for line in lines[-100:]:
        if '非同步包消息，跳过处理' in line:
            non_sync_messages.append(line.strip())
    
    print(f"\n📤 被跳过的非同步包消息: {len(non_sync_messages)} 条")
    if non_sync_messages:
        for msg in non_sync_messages[-3:]:  # 显示最后3条
            print(f"  {msg}")

def suggest_debug_steps():
    """建议调试步骤"""
    print(f"\n🔧 调试建议:")
    print("1. 86字节消息通常是心跳包或系统消息")
    print("2. 真正的聊天消息通常较大(>200字节)")
    print("3. 如果没有收到大消息，可能是：")
    print("   - 没有人给你发消息")
    print("   - WebSocket连接有问题")
    print("   - 账号状态异常")
    print("4. 建议:")
    print("   - 找个朋友给你的闲鱼账号发条消息")
    print("   - 观察是否出现大于200字节的WebSocket消息")
    print("   - 检查消息是否包含聊天内容")

if __name__ == "__main__":
    analyze_websocket_messages()
    suggest_debug_steps()