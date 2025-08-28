#!/usr/bin/env python3
"""
临时添加消息调试日志的脚本
"""

import os
import re
import time
from pathlib import Path

def apply_debug_patch():
    """应用调试补丁"""
    original_file = Path('XianyuAutoAsync.py')
    backup_file = Path('XianyuAutoAsync.py.backup')
    
    if not original_file.exists():
        print("❌ XianyuAutoAsync.py 文件不存在")
        return False
    
    # 备份原文件
    if not backup_file.exists():
        with open(original_file, 'r', encoding='utf-8') as f:
            content = f.read()
        with open(backup_file, 'w', encoding='utf-8') as f:
            f.write(content)
        print("✅ 已备份原文件")
    
    # 读取原文件
    with open(original_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查是否已经应用过补丁
    if '【调试】消息内容详情:' in content:
        print("⚠️ 调试补丁已经应用，无需重复应用")
        return True
    
    # 添加调试代码
    debug_pattern = r'(logger\.info\(f"【\{self\.cookie_id\}】收到WebSocket消息: \{len\(message\) if message else 0\} 字节"\))'
    debug_replacement = r'''\1
                            # 【调试】记录消息内容
                            try:
                                if message and len(message) > 100:  # 只记录较大的消息
                                    message_preview = str(message)[:500] + "..." if len(str(message)) > 500 else str(message)
                                    logger.info(f"【调试】消息内容详情: {message_preview}")
                                    
                                    # 解析JSON并记录结构
                                    try:
                                        message_data_debug = json.loads(message)
                                        logger.info(f"【调试】消息JSON结构: {json.dumps(message_data_debug, ensure_ascii=False, indent=2)[:1000]}")
                                    except:
                                        pass
                            except Exception as e:
                                logger.error(f"【调试】记录消息详情失败: {e}")'''
    
    new_content = re.sub(debug_pattern, debug_replacement, content, flags=re.MULTILINE)
    
    if new_content == content:
        print("❌ 未找到匹配的代码位置")
        return False
    
    # 写入修改后的文件
    with open(original_file, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print("✅ 调试补丁应用成功")
    return True

def restore_original():
    """恢复原文件"""
    original_file = Path('XianyuAutoAsync.py')
    backup_file = Path('XianyuAutoAsync.py.backup')
    
    if not backup_file.exists():
        print("❌ 备份文件不存在")
        return False
    
    with open(backup_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    with open(original_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ 已恢复原文件")
    return True

def main():
    """主函数"""
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'restore':
        restore_original()
    else:
        apply_debug_patch()
        print("\n🔧 使用方法:")
        print("1. 重启程序: python3 Start.py")
        print("2. 让朋友给你发消息")
        print("3. 观察日志中的【调试】信息")
        print("4. 恢复原文件: python3 debug_message_patch.py restore")

if __name__ == "__main__":
    main()