#!/usr/bin/env python3
"""
临时调试补丁 - 查看实际消息结构
"""

import json
import re
from pathlib import Path

def create_debug_patch():
    """创建调试补丁"""
    
    # 读取原始文件
    original_file = Path('XianyuAutoAsync.py')
    if not original_file.exists():
        print("❌ XianyuAutoAsync.py 文件不存在")
        return
    
    with open(original_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 查找 handle_message 方法中的 is_sync_package 检查
    pattern = r'(\s+# 如果不是同步包消息，直接返回\s+if not self\.is_sync_package\(message_data\):\s+logger\.info\(f"【\{self\.cookie_id\}】非同步包消息，跳过处理"\)\s+return)'
    
    # 替换为调试版本
    debug_code = '''
        # 【调试】记录消息结构
        try:
            logger.info(f"【调试】收到消息结构: {json.dumps(message_data, indent=2, ensure_ascii=False)[:500]}...")
            logger.info(f"【调试】消息字段: {list(message_data.keys())}")
            if "body" in message_data:
                logger.info(f"【调试】body字段: {list(message_data['body'].keys())}")
        except Exception as e:
            logger.info(f"【调试】消息结构记录失败: {e}")
        
        # 如果不是同步包消息，直接返回
        if not self.is_sync_package(message_data):
            logger.info(f"【{self.cookie_id}】非同步包消息，跳过处理")
            return'''
    
    if re.search(pattern, content):
        new_content = re.sub(pattern, debug_code, content)
        
        # 备份原文件
        backup_file = Path('XianyuAutoAsync.py.backup')
        with open(backup_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # 写入调试版本
        with open(original_file, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        print("✅ 调试补丁已应用")
        print("📁 原文件已备份为 XianyuAutoAsync.py.backup")
        print("🔄 需要重启程序来生效")
        
        return True
    else:
        print("❌ 未找到目标代码段，无法应用补丁")
        return False

def restore_original():
    """恢复原始文件"""
    backup_file = Path('XianyuAutoAsync.py.backup')
    original_file = Path('XianyuAutoAsync.py')
    
    if backup_file.exists():
        with open(backup_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        with open(original_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        backup_file.unlink()  # 删除备份文件
        print("✅ 原始文件已恢复")
        return True
    else:
        print("❌ 备份文件不存在")
        return False

def main():
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'restore':
        restore_original()
    else:
        print("=== 临时调试补丁 ===")
        print("这将临时修改 XianyuAutoAsync.py 来记录消息结构")
        print("应用补丁后需要重启程序")
        print()
        
        if create_debug_patch():
            print("\n下一步:")
            print("1. 重启程序: pkill -f Start.py && python3 Start.py &")
            print("2. 发送测试消息")
            print("3. 查看日志中的消息结构")
            print("4. 恢复原文件: python3 temp_debug_patch.py restore")

if __name__ == "__main__":
    main()