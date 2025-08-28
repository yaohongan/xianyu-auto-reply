#!/usr/bin/env python3
"""
设置AI专用回复模式的脚本
"""

from db_manager import db_manager

def set_ai_only_mode(cookie_id: str, only_ai: bool = True):
    """设置AI专用回复模式"""
    try:
        # 获取当前AI回复设置
        current_settings = db_manager.get_ai_reply_settings(cookie_id)
        
        # 更新设置
        current_settings['only_ai_reply'] = only_ai
        
        # 保存设置
        success = db_manager.save_ai_reply_settings(cookie_id, current_settings)
        
        if success:
            mode_text = "仅AI回复" if only_ai else "AI+关键词回复"
            print(f"✅ 已设置账号 {cookie_id} 为 {mode_text} 模式")
            
            # 显示当前设置
            print(f"\n当前AI回复设置:")
            print(f"  AI启用: {current_settings.get('ai_enabled', False)}")
            print(f"  仅AI回复: {current_settings.get('only_ai_reply', False)}")
            print(f"  模型: {current_settings.get('model_name', 'gpt-3.5-turbo')}")
            print(f"  API地址: {current_settings.get('base_url', 'https://api.openai.com/v1')}")
            
        else:
            print(f"❌ 设置失败")
        
    except Exception as e:
        print(f"❌ 设置过程中出错: {e}")

def main():
    """主函数"""
    print("🤖 AI专用回复模式设置")
    print("=" * 40)
    
    # 显示所有账号
    try:
        with db_manager.lock:
            cursor = db_manager.conn.cursor()
            cursor.execute('SELECT id FROM cookies')
            accounts = [row[0] for row in cursor.fetchall()]
        
        if not accounts:
            print("❌ 数据库中没有找到任何账号")
            return
        
        print("找到以下账号:")
        for i, account in enumerate(accounts, 1):
            print(f"  {i}. {account}")
        
        # 让用户选择账号
        try:
            choice = int(input(f"\n请选择账号 (1-{len(accounts)}): ")) - 1
            if 0 <= choice < len(accounts):
                cookie_id = accounts[choice]
            else:
                print("❌ 选择无效")
                return
        except ValueError:
            print("❌ 请输入有效数字")
            return
        
        # 让用户选择模式
        print(f"\n选择 {cookie_id} 的回复模式:")
        print("1. 仅AI回复 (推荐)")
        print("2. AI+关键词回复")
        
        try:
            mode_choice = int(input("请选择模式 (1-2): "))
            if mode_choice == 1:
                set_ai_only_mode(cookie_id, True)
            elif mode_choice == 2:
                set_ai_only_mode(cookie_id, False)
            else:
                print("❌ 选择无效")
                return
        except ValueError:
            print("❌ 请输入有效数字")
            return
            
    except Exception as e:
        print(f"❌ 操作失败: {e}")

if __name__ == "__main__":
    main()