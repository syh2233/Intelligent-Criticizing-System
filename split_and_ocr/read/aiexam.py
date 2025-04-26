from . import questionsplit
from . import fill_question
from . import true_false_questions
from . import multiple_choice_questions
from . import programming_questions
from . import short_answer_questions
# import questionsplit
# import fill_question
# import true_false_questions
# import multiple_choice_questions
# import programming_questions
# import short_answer_questions
import re
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 根据当前文件的位置正确导入模块
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from split_and_ocr.ai import new
import sqlite3
from split_and_ocr.read.db_utils import get_db_connection


class AIExam:
    #删除ocr识别的临时txt文件
    @staticmethod
    def remove_txt(name):
        files = [f for f in os.listdir() if f.endswith('.txt')]
        # 匹配包含指定名称且文件名长度大于2的文件
        fill_files = [f for f in files if re.search(rf'{name}.+', f)]
        if fill_files:
            os.remove(fill_files[0])
    
    #进行正统ai阅卷
    @staticmethod
    def run_slip(subject, session_id, ocr_file_path=None):
        print(f"当前工作目录: {os.getcwd()}")
        print(f"当前文件路径: {__file__}")
        print(f"Python路径: {sys.path}")

        # 初始化关键变量，确保在首次使用前已定义
        user = "未知用户"
        sid = "未知学号"
        global student_id
        count = 0

        try:
            # 测试数据库连接
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            print(f"数据库中的表: {[t[0] for t in tables]}")
        except Exception as e:
            print(f"数据库连接测试失败: {str(e)}")
            conn = None
            cursor = None

        # 从student_info.txt文件读取学生信息
        student_info = {}

        # 使用JSON格式分割方法处理学生答卷，传入指定的OCR文件路径
        try:
            print("开始使用JSON格式分割学生答卷...")
            student_info = questionsplit.readexit(ocr_file_path)

            if student_info:
                print(f"已获取学生信息:")
                for key, value in student_info.items():
                    if value:  # 只显示非空信息
                        print(f"  {key}: {value}")

                # 更新用户和学号变量
                if "姓名" in student_info:
                    user = student_info["姓名"]
                if "学号" in student_info:
                    sid = student_info["学号"]
            else:
                print("未能获取学生信息")
        except Exception as e:
            import traceback
            print(f"试卷分割失败: {str(e)}")
            print(traceback.format_exc())

        # 从文件读取学生信息
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            info_file = os.path.join(current_dir, "student_info.txt")
            if os.path.exists(info_file):
                with open(info_file, "r", encoding="utf-8") as f:
                    for line in f:
                        if ":" in line:
                            key, value = line.split(":", 1)
                            student_info[key.strip()] = value.strip()

                # 获取学生姓名和学号
                if "姓名" in student_info:
                    user = student_info["姓名"]
                if "学号" in student_info:
                    sid = student_info["学号"]

                print(f"从文件读取学生信息 - 姓名: {user}, 学号: {sid}")

                # 重新建立数据库连接
                try:
                    if conn is None:
                        conn = get_db_connection()
                        cursor = conn.cursor()

                    # 修复：使用逗号分隔参数传递给元组，而不是直接传递单个值
                    cursor.execute('SELECT id FROM students WHERE name = ? OR student_id = ?', (user, sid))
                    student_result = cursor.fetchone()

                    if student_result:
                        student_id = student_result[0]
                        print(f"找到学生记录，ID: {student_id}")
                    else:
                        print(f"在数据库中未找到学生 '{user}'，学号'{sid}'，将创建新学生记录")
                        # 插入新学生记录
                        cursor.execute('''
                            INSERT INTO students (name, student_id, user_id, created_at)
                            VALUES (?, ?, ?, datetime('now'))
                        ''', (user, sid, ""))
                        conn.commit()
                        student_id = cursor.lastrowid
                        print(f"已创建新学生记录，ID: {student_id}")
                except Exception as db_error:
                    print(f"数据库操作失败: {str(db_error)}")
                    import traceback
                    print(traceback.format_exc())
                    # 确保有一个有效的student_id
                    if student_id is None:
                        student_id = -1
                        print(f"使用默认学生ID: {student_id}")
            else:
                print("警告: 未找到student_info.txt文件，使用默认值")
        except Exception as e:
            print(f"读取学生信息文件失败: {str(e)}")
            import traceback
            print(traceback.format_exc())

        # 再次确保student_id已定义
        if student_id is None:
            try:
                # 创建默认学生记录
                if conn is None:
                    conn = get_db_connection()
                    cursor = conn.cursor()

                print(f"创建默认学生记录，姓名: {user}, 学号: {sid}")
                cursor.execute('''
                    INSERT INTO students (name, student_id, user_id, created_at)
                    VALUES (?, ?, ?, datetime('now'))
                ''', (user, sid, ""))
                conn.commit()
                student_id = cursor.lastrowid
                print(f"已创建默认学生记录，ID: {student_id}")
            except Exception as error:
                print(f"创建默认学生记录失败: {str(error)}")
                import traceback
                print(traceback.format_exc())
                student_id = -1  # 使用默认ID
                print(f"使用应急学生ID: {student_id}")

        print(f"开始AI阅卷 - 科目: {subject}, 用户: {user}, 考试ID: {session_id}, 学生ID: {student_id}")

        # 确保全局可以访问学生ID
        # global student_id

        # 以下是评分部分，处理各种题型...
        try:
            # 进行选择题评分
            print("开始选择题评分...")
            multiple_score, student_answers, correct_answers, scores = multiple_choice_questions.choice_grading(subject, session_id, student_id)
            count += multiple_score  # 直接加上选择题的得分
            print(f"选择题评分完成，得分: {multiple_score}")
        except Exception as e:
            import traceback
            print(f"选择题评分失败: {str(e)}")
            print(traceback.format_exc())

        try:
            # 进行填空题评分
            print("开始填空题评分...")
            _, _, fill_score = fill_question.fill_readexit(subject, session_id, student_id)
            count += fill_score  # 直接加上填空题的得分
            print(f"填空题评分完成，得分: {fill_score}")
        except Exception as e:
            import traceback
            print(f"填空题评分失败: {str(e)}")
            print(traceback.format_exc())

        try:
            # 进行编程题评分
            print("开始编程题评分...")
            _, _, pro_score = programming_questions.pro_grading(subject, session_id, student_id)
            count += pro_score
            print(f"编程题评分完成，得分: {pro_score}")
        except Exception as e:
            print(f"编程题评分失败: {str(e)}")

        try:
            # 进行简答题评分
            print("开始简答题评分...")
            _, _, short_score = short_answer_questions.answer_grading(subject, session_id, student_id)
            count += short_score
            print(f"简答题评分完成，得分: {short_score}")
        except Exception as e:
            print(f"简答题评分失败: {str(e)}")

        try:
            # 进行判断题评分
            print("开始判断题评分...")
            _, _, tf_score = true_false_questions.tf_grading(subject, session_id, student_id)
            count += tf_score
            print(f"判断题评分完成，得分: {tf_score}")
        except Exception as e:
            print(f"判断题评分失败: {str(e)}")

        # 保存总分和学生信息到数据库
        try:
            # 确保使用新的数据库连接
            new_conn = get_db_connection()
            new_cursor = new_conn.cursor()

            # 更新学生考试分数
            new_cursor.execute('''
                INSERT OR REPLACE INTO student_exams 
                (student_id, session_id, status, start_time, completion_time, score, pass_status)
                VALUES (?, ?, 'completed', datetime('now'), datetime('now'), ?, ?)
            ''', (student_id, session_id, count, count >= 60))
            print(f"保存学生成绩 {count} 分到数据库，学生ID: {student_id}, 考试ID: {session_id}, 状态: 已完成")

            new_conn.commit()
            new_conn.close()
        except Exception as e:
            import traceback
            print(f"保存学生分数和信息失败: {str(e)}")
            print(traceback.format_exc())

        # 清理临时文件
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            # 删除所有生成的临时txt文件
            for filename in os.listdir(current_dir):
                if filename.endswith('.txt') and filename not in ['@ocr_results.txt', 'ocr_results.txt',
                                                                  'oocr_results.txt', 'student_info.txt']:
                    try:
                        os.remove(os.path.join(current_dir, filename))
                        print(f"已删除临时文件: {filename}")
                    except:
                        pass
        except Exception as e:
            print(f"清理临时文件失败: {str(e)}")

        # 关闭数据库连接
        if conn:
            try:
                conn.close()
            except:
                pass

        print(f"AI阅卷完成，总得分: {count}")
        return user, sid

    #新增试卷时，ocr识别，更新题库
    @staticmethod
    def run_ocr(subject, user_id, session_id):
        try:
            print(f"当前工作目录: {os.getcwd()}")
            print(f"当前文件路径: {__file__}")
            print(f"Python路径: {sys.path}")
            
            # 测试数据库连接
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = cursor.fetchall()
                print(f"数据库中的表: {[t[0] for t in tables]}")
                conn.close()
            except Exception as e:
                print(f"数据库连接测试失败: {str(e)}")
            
            try:
                print("开始使用JSON格式分割原始试卷...")
                questionsplit.oreadexit()
                print("原始试卷分割完成")
            except Exception as e:
                import traceback
                print(f"题目分割失败: {str(e)}")
                print(traceback.format_exc())
            
            try:
                fill_question.ofill_readexit(subject, user_id, session_id)
            except Exception as e:
                print(f"填空题读取失败: {str(e)}")
            try:
                multiple_choice_questions.choice_readexit(subject, user_id, session_id)
            except Exception as e:
                print(f"选择题读取失败: {str(e)}")
            try:
                programming_questions.pro_readexit(subject, user_id, session_id)
            except Exception as e:
                print(f"编程题读取失败: {str(e)}")
            try:
                short_answer_questions.answer_readexit(subject, user_id, session_id)
            except Exception as e:
                print(f"简答题读取失败: {str(e)}")
            try:
                true_false_questions.tf_readexit(subject, user_id, session_id)
            except Exception as e:
                print(f"判断题读取失败: {str(e)}")
            AIExam.adjust_question_scores(subject, session_id)
            print("题库更新完成")
            
            # 清理临时txt文件
            try:
                print("开始清理临时txt文件...")
                current_dir = os.path.dirname(os.path.abspath(__file__))
                removed_count = 0
                
                # 删除各类题目生成的临时文件
                for category in ["填空", "选择", "编程", "简答", "判断", "一"]:
                    files = [f for f in os.listdir(current_dir) if f.endswith('.txt') and 
                             (category in f) and not f.startswith('@') and not f.startswith('ocr_')]
                    for file in files:
                        try:
                            os.remove(os.path.join(current_dir, file))
                            removed_count += 1
                            print(f"已删除临时文件: {file}")
                        except Exception as e:
                            print(f"删除文件 {file} 失败: {str(e)}")
                
                print(f"清理完成，共删除 {removed_count} 个临时文件")
            except Exception as e:
                print(f"清理临时文件过程中发生错误: {str(e)}")
                
            return True
        except Exception as e:
            print(f"题库更新失败: {str(e)}")
            return False

    @staticmethod
    def adjust_question_scores(subject, session_id):
        """
        查询当前考试的所有题目，根据难度调整分数，使总分符合考试要求
        """
        try:
            # 连接数据库
            current_dir = os.getcwd()
            db_path = os.path.join(current_dir, 'database', 'It_g.db')
            print(f"尝试连接数据库: {db_path}")
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # 添加调试代码
            print(f"当前工作目录: {os.getcwd()}")
            
            # 获取考试总分
            cursor.execute('''
                SELECT exam_score FROM exam_sessions 
                WHERE id = ? AND subject = ?
            ''', (session_id, subject))
            exam_session = cursor.fetchone()
            
            if not exam_session:
                print(f"未找到考试: {subject}, session_id={session_id}")
                return False
                
            target_total_score = exam_session[0]
            
            # 获取当前所有题目及其难度
            cursor.execute('''
                SELECT id, question_type, score, question_order, source_question_id, source_table 
                FROM questions 
                WHERE session_id = ?
            ''', (session_id,))
            questions = cursor.fetchall()
            
            if not questions:
                print(f"未找到考试题目: session_id={session_id}")
                return False
                
            # 收集所有题目的难度信息
            questions_with_difficulty = []
            for q in questions:
                q_id, q_type, score, q_order, source_id, source_table = q
                
                # 如果有source_table和source_id，从源表获取难度
                if source_table and source_id:
                    cursor.execute(f'''
                        SELECT difficulty FROM {source_table}
                        WHERE id = ?
                    ''', (source_id,))
                    result = cursor.fetchone()
                    difficulty = result[0] if result else 3  # 默认中等难度
                else:
                    difficulty = 3  # 默认中等难度
                
                questions_with_difficulty.append({
                    'id': q_id, 
                    'type': q_type, 
                    'score': score, 
                    'order': q_order, 
                    'difficulty': difficulty
                })
            
            # 计算当前总分
            current_total_score = sum(q['score'] for q in questions_with_difficulty)
            
            # 修改调用AI部分
            prompt = f"""
            我有一套考试题，需要根据题目难度调整分数，使总分从{current_total_score}调整到{target_total_score}分。
            题目信息如下：
            {[f"题号:{q['order']}, 类型:{q['type']}, 难度:{q['difficulty']}, 当前分数:{q['score']}" for q in questions_with_difficulty]}
            
            请按照以下规则调整每道题的分数：
            1. 难度越高的题目，分数应该越高
            2. 相同难度下，编程题和简答题分数应高于选择题和填空题
            3. 所有题目分数必须为正整数
            4. 调整后的总分必须等于{target_total_score}
            
            请只返回JSON格式的结果，不要有任何其他文字，格式为：[{{"order": 1, "score": 10}}, {{"order": 2, "score": 15}}]
            """
            
            response = new(
                "你是一个专业的教育领域助手，擅长合理分配考试分数。请根据题目难度和类型分配合理的分数。请仅返回JSON格式，不要有任何其他文字。",
                prompt
            )
            
            try:
                # 添加调试输出
                print(f"AI返回原始内容: {response}")
                
                # 处理返回内容，移除可能的前缀和后缀文本
                json_str = response.strip()
                
                # 查找第一个[和最后一个]之间的内容
                start = json_str.find('[')
                end = json_str.rfind(']') + 1
                if start >= 0 and end > start:
                    json_str = json_str[start:end]
                
                import json
                adjusted_scores = json.loads(json_str)
                print(f"解析后的JSON: {adjusted_scores}")
                
                # 更新数据库中的分数
                for score_info in adjusted_scores:
                    order = score_info['order']
                    new_score = score_info['score']
                    
                    # 查找对应题号的题目ID
                    matching_question = next((q for q in questions_with_difficulty if q['order'] == order), None)
                    if matching_question:
                        cursor.execute('''
                            UPDATE questions 
                            SET score = ? 
                            WHERE id = ?
                        ''', (new_score, matching_question['id']))
                
                conn.commit()
                print(f"成功调整考试题目分数，总分为: {target_total_score}")
                return True
            except Exception as e:
                print(f"分数调整失败: {str(e)}")
                print(f"AI返回内容: {response}")
                conn.rollback()
                return False
            
        except Exception as e:
            print(f"题目分数调整失败: {str(e)}")
            return False
        finally:
            if 'conn' in locals():
                conn.close()

# 创建一个实例供外部使用
aiexam = AIExam()

if __name__ == '__main__': 
    AIExam.run_ocr("java", 1, 1)
    # 启动阅卷
    # count = AIExam.run_slip("java", 1, 1)
    # print(f"最终得分: {count}")