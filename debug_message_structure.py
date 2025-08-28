#!/usr/bin/env python3
"""
调试消息结构脚本
"""

import json
import time
from pathlib import Path

def analyze_recent_messages():
    """分析最近收到的消息"""
    print("=== 消息结构分析 ===")
    
    # 从日志中提取消息大小信息
    log_file = f'logs/xianyu_{time.strftime("%Y-%m-%d")}.log'
    if not Path(log_file).exists():
        print("❌ 日志文件不存在")
        return
    
    with open(log_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # 查找WebSocket消息
    message_sizes = []
    for line in lines[-100:]:  # 检查最后100行
        if '收到WebSocket消息:' in line and '字节' in line:
            try:
                # 提取消息大小
                size_part = line.split('收到WebSocket消息:')[1].split('字节')[0].strip()
                size = int(size_part)
                message_sizes.append(size)
            except:
                continue
    
    if message_sizes:
        print(f"最近收到 {len(message_sizes)} 条消息")
        print(f"消息大小分布: {set(message_sizes)}")
        
        # 分析消息类型
        size_counts = {}
        for size in message_sizes:
            size_counts[size] = size_counts.get(size, 0) + 1
        
        print("\n消息大小统计:")
        for size, count in sorted(size_counts.items()):
            print(f"  {size} 字节: {count} 条")
            
        # 86字节通常是心跳包
        if 86 in size_counts:
            print(f"\n⚠️  发现 {size_counts[86]} 条 86字节消息（可能是心跳包）")
        
        # 查找可能的用户消息（通常大于100字节）
        user_message_sizes = [s for s in size_counts.keys() if s > 100]
        if user_message_sizes:
            print(f"✅ 发现可能的用户消息: {user_message_sizes} 字节")
        else:
            print("❌ 没有发现用户消息（所有消息都小于100字节）")
    else:
        print("❌ 没有找到WebSocket消息记录")

def check_message_processing_logic():
    """检查消息处理逻辑"""
    print("\n=== 消息处理逻辑检查 ===")
    
    # 模拟不同类型的消息结构
    test_messages = [
        # 心跳包结构
        {
            "headers": {"mid": "test"},
            "body": {}
        },
        # 可能的同步包结构
        {
            "headers": {"mid": "test"},
            "body": {
                "syncPushPackage": {
                    "data": [{"data": "test_data"}]
                }
            }
        },
        # 空的同步包
        {
            "headers": {"mid": "test"},
            "body": {
                "syncPushPackage": {
                    "data": []
                }
            }
        }
    ]
    
    # 模拟 is_sync_package 逻辑
    def test_is_sync_package(message_data):
        try:
            return (
                isinstance(message_data, dict)
                and "body" in message_data
                and "syncPushPackage" in message_data["body"]
                and "data" in message_data["body"]["syncPushPackage"]
                and len(message_data["body"]["syncPushPackage"]["data"]) > 0
            )
        except Exception:
            return False
    
    for i, msg in enumerate(test_messages, 1):
        result = test_is_sync_package(msg)
        print(f"测试消息 {i}: {'✅ 同步包' if result else '❌ 非同步包'}")
        print(f"  结构: {json.dumps(msg, ensure_ascii=False)}")

def main():
    analyze_recent_messages()
    check_message_processing_logic()
    
    print("\n=== 建议 ===")
    print("1. 如果只收到86字节的心跳包，说明没有真实用户消息")
    print("2. 需要有用户实际发送消息才能测试AI回复功能")
    print("3. 可以通过闲鱼APP向你的商品发送消息来测试")
    print("4. 或者使用Web界面的AI回复测试功能")

if __name__ == "__main__":
    main()