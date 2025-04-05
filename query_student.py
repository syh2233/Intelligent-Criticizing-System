import sqlite3
from datetime import datetime
import os

def get_db_connection():
    # 直接连接到数据库文件
    conn = sqlite3.connect('database/It_g.db')
    conn.row_factory = sqlite3.Row
    return conn

def list_all_tables(cursor):
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print("数据库中的所有表：")
    for table in tables:
        print(f"- {table['name']}")
    return [table['name'] for table in tables]

def insert_questions():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 列出所有表
        tables = list_all_tables(cursor)
        
        # 确认我们要操作的表名
        questions_table = None
        for table in tables:
            if table.lower() == 'questions':
                questions_table = table
                break
        
        if not questions_table:
            raise Exception("找不到questions表，可用的表有: " + ", ".join(tables))
        
        # 找到所有可能的题库表
        source_tables = {
            'multiple_choice': None,
            'fill_blank': None,
            'true_false': None,
            'short_answer': None,
            'programming': None
        }
        
        for table in tables:
            if 'multiple_choice' in table.lower():
                source_tables['multiple_choice'] = table
            elif 'fill_blank' in table.lower():
                source_tables['fill_blank'] = table
            elif 'true_false' in table.lower():
                source_tables['true_false'] = table
            elif 'short_answer' in table.lower():
                source_tables['short_answer'] = table
            elif 'programming' in table.lower():
                source_tables['programming'] = table
        
        print("\n找到的题库表：")
        for key, value in source_tables.items():
            print(f"- {key}: {value}")
        
        # 设置考试ID
        session_id = 2
        
        # 获取questions表的列名
        cursor.execute(f"PRAGMA table_info({questions_table})")
        columns = [column[1] for column in cursor.fetchall()]
        print(f"\nquestions表的列: {', '.join(columns)}")
        
        # 根据实际列名构建INSERT语句
        if all(col in columns for col in ['session_id', 'question_type', 'question_text', 'score', 'question_order', 'source_question_id', 'source_table']):
            # 从各个题库表中获取Python相关的题目
            for q_type, table_name in source_tables.items():
                if not table_name:
                    print(f"跳过 {q_type} 题型，未找到对应表")
                    continue
                
                print(f"正在处理 {q_type} 题型，表名: {table_name}")
                
                # 获取源表的列名
                cursor.execute(f"PRAGMA table_info({table_name})")
                source_columns = [column[1] for column in cursor.fetchall()]
                
                if 'subject' in source_columns and 'question_text' in source_columns and 'score' in source_columns:
                    try:
                        cursor.execute(f'''
                            INSERT INTO {questions_table} (session_id, question_type, question_text, score, question_order, source_question_id, source_table)
                            SELECT ?, ?, question_text, score, ROW_NUMBER() OVER (ORDER BY id), id, ?
                            FROM {table_name}
                            WHERE subject LIKE '%Python%'
                        ''', (session_id, q_type, table_name))
                        print(f"成功从 {table_name} 插入题目")
                    except sqlite3.Error as e:
                        print(f"插入 {q_type} 题目时出错: {e}")
                else:
                    print(f"表 {table_name} 缺少必要的列: subject, question_text, score")
        else:
            print("questions表缺少必要的列，无法执行插入操作")
            missing_cols = [col for col in ['session_id', 'question_type', 'question_text', 'score', 'question_order', 'source_question_id', 'source_table'] if col not in columns]
            print(f"缺少的列: {', '.join(missing_cols)}")
        
        # 提交更改
        conn.commit()
        
        # 获取插入的题目数量
        cursor.execute(f'''
            SELECT COUNT(*) as count
            FROM {questions_table}
            WHERE session_id = ?
        ''', (session_id,))
        
        count = cursor.fetchone()['count']
        print(f"成功插入 {count} 道题目到考试ID {session_id}")
        
    except Exception as e:
        print(f"发生错误: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == '__main__':
    insert_questions() 