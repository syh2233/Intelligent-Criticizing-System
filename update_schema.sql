-- 添加 final_score 列到 student_answers 表
ALTER TABLE student_answers ADD COLUMN final_score REAL CHECK(final_score >= 0);

-- 更新现有记录，将 ai_score 复制到 final_score
UPDATE student_answers SET final_score = ai_score WHERE final_score IS NULL;

-- 添加 manual_feedback 列到 student_answers 表
ALTER TABLE student_answers ADD COLUMN manual_feedback TEXT; 