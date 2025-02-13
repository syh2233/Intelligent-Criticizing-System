import sqlite3
from datetime import datetime, timedelta
import json

def insert_test_data():
    # 连接数据库
    conn = sqlite3.connect('database/It_g.db')
    cursor = conn.cursor()
    
    try:
        # 1. 插入教师用户
        cursor.execute('''
            INSERT INTO users (email, password) 
            VALUES (?, ?)
        ''', ('teacher@test.com', '123456'))
        teacher_id = cursor.lastrowid
        
        # 2. 插入学生数据
        students_data = [
            ('沈亦豪', '2021001'),
            ('刘少辉', '2021002'),
            ('张自立', '2021003'),
            ('俞章琳', '2021004'),
            ('陈谢凯', '2021005'),
            ('王培吉', '2021006'),
            ('姚景祥', '2021007')
        ]
        
        student_ids = []
        for name, student_id in students_data:
            cursor.execute('''
                INSERT INTO students (name, student_id, user_id)
                VALUES (?, ?, NULL)
            ''', (name, student_id))
            student_ids.append(cursor.lastrowid)
        
        # 3. 创建考试场次
        now = datetime.now()
        exam_start = now - timedelta(days=1)  # 昨天开始（便于添加已完成的成绩）
        exam_end = exam_start + timedelta(hours=2)
        
        cursor.execute('''
            INSERT INTO exam_sessions 
            (name, subject, start_time, end_time, duration, exam_file_path, exam_score, status, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('2024年春季人工智能期中考试', '人工智能', exam_start, exam_end, 120, 
              'uploads/ai_exam.pdf', 100, 'graded', teacher_id))
        
        session_id = cursor.lastrowid
        
        # 4. 创建题库题目
        # 4.1 选择题 (20分)
        cursor.execute('''
            INSERT INTO multiple_choice_questions 
            (subject, question_text, option_a, option_b, option_c, option_d, 
             correct_answer, explanation, score, difficulty, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('人工智能', '以下哪个不是机器学习的主要类型？',
              'A. 监督学习', 'B. 无监督学习', 'C. 强化学习', 'D. 演绎学习',
              'D', '机器学习主要包括监督学习、无监督学习和强化学习三种类型', 20, 3, teacher_id))
        mc_question_id = cursor.lastrowid
        
        # 4.2 填空题 (10分)
        cursor.execute('''
            INSERT INTO fill_blank_questions 
            (subject, question_text, correct_answer, explanation, score, difficulty, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', ('人工智能', '神经网络中用于防止过拟合的技术是____。',
              'Dropout', '防止过拟合的常用技术包括Dropout、L1/L2正则化等', 10, 3, teacher_id))
        fb_question_id = cursor.lastrowid
        
        # 4.3 判断题 (10分)
        cursor.execute('''
            INSERT INTO true_false_questions 
            (subject, question_text, correct_answer, explanation, score, difficulty, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', ('人工智能', '深度学习是机器学习的一个子集。',
              True, '深度学习是机器学习的一个重要分支，主要基于深层神经网络', 10, 2, teacher_id))
        tf_question_id = cursor.lastrowid
        
        # 4.4 简答题 (30分)
        cursor.execute('''
            INSERT INTO short_answer_questions 
            (subject, question_text, reference_answer, key_points, grading_criteria, score, difficulty, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('人工智能', '请解释卷积神经网络(CNN)的基本原理和主要组成部分。',
              '卷积神经网络主要由卷积层、池化层和全连接层组成...', 
              '卷积操作原理;池化层作用;全连接层功能',
              '完整性(10分);准确性(10分);举例说明(10分)', 30, 4, teacher_id))
        sa_question_id = cursor.lastrowid
        
        # 4.5 编程题 (30分)
        cursor.execute('''
            INSERT INTO programming_questions 
            (subject, question_text, sample_input, sample_output, test_cases, reference_solution,
             time_limit, memory_limit, score, difficulty, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('人工智能', '实现一个简单的神经网络前向传播算法',
              'X = [[1, 2], [3, 4]]', 'Y = [[0.8], [0.9]]',
              '{"test1": {"input": [[1,2]], "output": [[0.8]]}}',
              'def forward(X, weights): ...',
              1000, 256, 30, 4, teacher_id))
        prog_question_id = cursor.lastrowid
        
        # 5. 将题目添加到考试中
        questions_data = [
            (session_id, 'multiple_choice', '以下哪个不是机器学习的主要类型？', 20, 1, mc_question_id),
            (session_id, 'fill_blank', '神经网络中用于防止过拟合的技术是____。', 10, 2, fb_question_id),
            (session_id, 'true_false', '深度学习是机器学习的一个子集。', 10, 3, tf_question_id),
            (session_id, 'short_answer', '请解释卷积神经网络(CNN)的基本原理和主要组成部分。', 30, 4, sa_question_id),
            (session_id, 'programming', '实现一个简单的神经网络前向传播算法', 30, 5, prog_question_id)
        ]
        
        question_ids = []
        for q_data in questions_data:
            cursor.execute('''
                INSERT INTO questions 
                (session_id, question_type, question_text, score, question_order, source_question_id)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', q_data)
            question_ids.append(cursor.lastrowid)
            
        # 6. 添加学生答案和成绩
        for idx, student_id in enumerate(student_ids):
            # 模拟不同水平的学生成绩
            scores = [
                (20, 10, 10, 28, 25),  # 优秀 93分
                (20, 8, 10, 25, 20),   # 良好 83分
                (15, 10, 10, 20, 15),  # 中等 70分
                (10, 5, 10, 15, 15),   # 及格 55分
                (5, 5, 5, 10, 10),     # 不及格 35分
                (20, 5, 10, 20, 20),   # 良好 75分
                (15, 8, 10, 22, 18),   # 中等 73分
            ][idx]
            
            for q_idx, (question_id, score) in enumerate(zip(question_ids, scores)):
                scoring_details = {
                    'accuracy': score * 0.8,
                    'completion': score * 0.9,
                    'explanation': score * 0.7
                }
                
                cursor.execute('''
                    INSERT INTO student_answers 
                    (session_id, student_id, question_id, question_type, answer_text,
                     ai_score, ai_feedback, scoring_details, review_status, reviewed_by,
                     reviewed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    session_id, student_id, question_id, questions_data[q_idx][1],
                    f"学生{idx+1}的答案内容...", score, "AI评分反馈...",
                    json.dumps(scoring_details), 'reviewed', teacher_id,
                    datetime.now()
                ))
        
        # 7. 添加题目分析数据
        for q_idx, question_id in enumerate(question_ids):
            cursor.execute('''
                INSERT INTO question_analysis 
                (session_id, question_id, average_score_rate, difficulty_coefficient, discrimination_degree)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                session_id, question_id,
                0.75,  # 平均得分率
                0.65,  # 难度系数
                0.45   # 区分度
            ))
        
        # 8. 添加成绩统计数据
        cursor.execute('''
            INSERT INTO score_statistics 
            (session_id, average_score, pass_rate, highest_score, highest_score_student_id)
            VALUES (?, ?, ?, ?, ?)
        ''', (session_id, 69.14, 0.71, 93, student_ids[0]))
        
        # 9. 添加分数分布数据
        score_ranges = [
            ('90-100', 1),
            ('80-89', 1),
            ('70-79', 2),
            ('60-69', 1),
            ('0-59', 2)
        ]
        
        for score_range, count in score_ranges:
            cursor.execute('''
                INSERT INTO score_distribution 
                (session_id, score_range, student_count)
                VALUES (?, ?, ?)
            ''', (session_id, score_range, count))
            
        # 提交事务
        conn.commit()
        print("测试数据插入成功！")
        
    except Exception as e:
        conn.rollback()
        print(f"插入数据时出错: {str(e)}")
        
    finally:
        conn.close()

if __name__ == '__main__':
    insert_test_data()
