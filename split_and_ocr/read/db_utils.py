import sqlite3
import json
import os
import re

def insert_student_answers_to_db(conn, session_id, student_id, question_id, question_type, answer_text, ai_score, ai_feedback="", scoring_details=""):
    """
    将学生答案插入到student_answers表
    
    参数:
    conn: 数据库连接
    session_id: 考试场次ID
    student_id: 学生ID
    question_id: 题目ID
    question_type: 题目类型(multiple_choice, fill_blank, short_answer, true_false, programming)
    answer_text: 学生答案文本
    ai_score: AI评分
    ai_feedback: AI反馈
    scoring_details: 评分详情
    """
    cursor = conn.cursor()
    
    # 插入数据
    cursor.execute('''
        INSERT INTO student_answers (
            session_id, 
            student_id, 
            question_id, 
            question_type, 
            answer_text, 
            ai_score, 
            ai_feedback, 
            scoring_details,
            final_score,
            review_status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
    ''', (session_id, student_id, question_id, question_type, answer_text, ai_score, ai_feedback, scoring_details, ai_score))
    
    conn.commit()
    return cursor.lastrowid

def insert_question_to_db(conn, session_id, question_type, question_text, score, question_order=None):
    """
    在数据库中找不到匹配题目时，向questions表中插入新题目
    
    参数:
    conn: 数据库连接
    session_id: 考试场次ID
    question_type: 题目类型(multiple_choice, fill_blank, short_answer, true_false, programming)
    question_text: 题目文本
    score: 题目分数
    question_order: 题目顺序，如果为None则自动计算
    
    返回:
    新插入题目的ID
    """
    cursor = conn.cursor()
    
    # 如果未指定题目顺序，获取当前最大顺序号+1
    if question_order is None:
        cursor.execute('''
            SELECT MAX(question_order) as max_order FROM questions 
            WHERE session_id = ? AND question_type = ?
        ''', (session_id, question_type))
        result = cursor.fetchone()
        max_order = result[0] if result and result[0] is not None else 0
        question_order = max_order + 1
    
    # 插入新题目
    cursor.execute('''
        INSERT INTO questions (
            session_id, 
            question_type, 
            question_text, 
            score, 
            question_order, 
            source_question_id, 
            source_table
        )
        VALUES (?, ?, ?, ?, ?, NULL, NULL)
    ''', (session_id, question_type, question_text, score, question_order))
    
    # 获取新插入的ID
    new_question_id = cursor.lastrowid
    conn.commit()
    
    print(f"已创建新题目: ID={new_question_id}, 类型={question_type}, 分数={score}")
    return new_question_id

def get_question_id(conn, session_id, source_question_id, source_table):
    """
    获取questions表中匹配的题目ID
    
    参数:
    conn: 数据库连接
    session_id: 考试场次ID
    source_question_id: 源题目ID
    source_table: 源表名
    
    返回:
    questions表中的ID或None
    """
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id FROM questions 
        WHERE session_id = ? AND source_question_id = ? AND source_table = ?
    ''', (session_id, source_question_id, source_table))
    result = cursor.fetchone()
    return result[0] if result else None

def get_question_score(conn, session_id, source_question_id, source_table):
    """
    获取questions表中题目的分数
    
    参数:
    conn: 数据库连接
    session_id: 考试场次ID
    source_question_id: 源题目ID
    source_table: 源表名
    
    返回:
    questions表中记录的分数或None
    """
    cursor = conn.cursor()
    cursor.execute('''
        SELECT score FROM questions 
        WHERE session_id = ? AND source_question_id = ? AND source_table = ?
    ''', (session_id, source_question_id, source_table))
    result = cursor.fetchone()
    return result[0] if result else None

def get_question_from_text(conn, session_id, question_text, question_type):
    """
    通过题目文本在questions表中查找题目
    
    参数:
    conn: 数据库连接
    session_id: 考试场次ID
    question_text: 题目文本
    question_type: 题目类型
    
    返回:
    (题目ID, 分数)元组或(None, None)
    """
    cursor = conn.cursor()
    
    # 使用前缀匹配对选择题进行优化处理
    if question_type == 'multiple_choice':
        # 清理文本
        clean_text = re.sub(r'[()（）.，、；：]', '', question_text).strip()
        
        # 获取前缀
        prefix_length = min(20, len(clean_text))
        prefix = clean_text[:prefix_length] + '%'
        
        # 首先尝试使用前缀匹配
        cursor.execute('''
            SELECT id, score FROM questions 
            WHERE session_id = ? AND question_type = ? AND question_text LIKE ?
        ''', (session_id, question_type, prefix))
        
        result = cursor.fetchone()
        if result:
            print(f"通过前缀匹配找到题目: 前缀='{prefix[:15]}...'")
            return result[0], result[1]
            
        # 针对Java题目的特殊处理
        if "java应用程序" in clean_text.lower() or "独立运行" in clean_text.lower():
            cursor.execute('''
                SELECT id, score FROM questions 
                WHERE session_id = ? AND question_type = ? AND 
                (question_text LIKE '%java应用程序%' OR question_text LIKE '%独立运行%')
            ''', (session_id, question_type))
            
            result = cursor.fetchone()
            if result:
                print(f"通过Java应用程序关键词匹配到题目")
                return result[0], result[1]
    
    # 一般情况 - 使用部分匹配
    search_text = f"%{question_text[:50]}%"  # 仅使用前50个字符进行模糊匹配
    cursor.execute('''
        SELECT id, score FROM questions 
        WHERE session_id = ? AND question_type = ? AND question_text LIKE ?
    ''', (session_id, question_type, search_text))
    
    result = cursor.fetchone()
    return (result[0], result[1]) if result else (None, None)

def get_db_connection():
    """
    获取数据库连接
    
    返回:
    SQLite连接对象
    """
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'database', 'It_g.db')
    return sqlite3.connect(db_path) 