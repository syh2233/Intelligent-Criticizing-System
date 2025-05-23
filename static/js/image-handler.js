// 图片处理函数\nwindow.makeImageDraggable = function(imgElement) {\n    console.log('函数被调用');\n    imgElement.classList.add('embedded-image');\n    return imgElement;\n};
console.log("修复makeImageDraggable问题");

// 定义全局makeImageDraggable函数
window.makeImageDraggable = function(imgElement) {
    console.log('makeImageDraggable函数被调用', imgElement);
    
    // 设置图片的基本样式
    imgElement.style.cursor = 'move';
    imgElement.style.display = 'inline-block';
    imgElement.style.margin = '5px';
    
    // 创建图片工具条
    const toolbar = document.createElement('div');
    toolbar.className = 'image-toolbar';
    toolbar.innerHTML = `
        <button title="左对齐"><i class="fas fa-align-left"></i></button>
        <button title="居中"><i class="fas fa-align-center"></i></button>
        <button title="右对齐"><i class="fas fa-align-right"></i></button>
        <button title="调整大小"><i class="fas fa-expand"></i></button>
        <button title="删除图片"><i class="fas fa-trash"></i></button>
    `;
    
    // 为图片创建外层容器，以便放置工具条
    const container = document.createElement('div');
    container.style.position = 'relative';
    container.style.display = 'inline-block';
    
    // 如果图片已经在DOM树中，替换它
    if (imgElement.parentNode) {
        imgElement.parentNode.insertBefore(container, imgElement);
        imgElement.parentNode.removeChild(imgElement);
    }
    
    // 将工具条和图片添加到容器中
    container.appendChild(toolbar);
    container.appendChild(imgElement);
    
    // 绑定工具条按钮事件
    const buttons = toolbar.querySelectorAll('button');
    
    // 左对齐
    buttons[0].addEventListener('click', function(e) {
        e.stopPropagation();
        container.style.display = 'block';
        container.style.textAlign = 'left';
        container.style.width = '100%';
        // 同步到textarea
        const questionContent = document.getElementById('question-content');
        const editorContent = document.getElementById('editor-content');
        if(editorContent && questionContent) {
            questionContent.value = editorContent.innerHTML;
        }
    });
    
    // 居中对齐
    buttons[1].addEventListener('click', function(e) {
        e.stopPropagation();
        container.style.display = 'block';
        container.style.textAlign = 'center';
        container.style.width = '100%';
        // 同步到textarea
        const questionContent = document.getElementById('question-content');
        const editorContent = document.getElementById('editor-content');
        if(editorContent && questionContent) {
            questionContent.value = editorContent.innerHTML;
        }
    });
    
    // 右对齐
    buttons[2].addEventListener('click', function(e) {
        e.stopPropagation();
        container.style.display = 'block';
        container.style.textAlign = 'right';
        container.style.width = '100%';
        // 同步到textarea
        const questionContent = document.getElementById('question-content');
        const editorContent = document.getElementById('editor-content');
        if(editorContent && questionContent) {
            questionContent.value = editorContent.innerHTML;
        }
    });
    
    // 调整大小
    buttons[3].addEventListener('click', function(e) {
        e.stopPropagation();
        const width = prompt('请输入图片宽度 (px)', imgElement.width || 300);
        if (width && !isNaN(width)) {
            imgElement.style.width = width + 'px';
            // 同步到textarea
            const questionContent = document.getElementById('question-content');
            const editorContent = document.getElementById('editor-content');
            if(editorContent && questionContent) {
                questionContent.value = editorContent.innerHTML;
            }
        }
    });
    
    // 删除图片
    buttons[4].addEventListener('click', function(e) {
        e.stopPropagation();
        if (confirm('确定要删除这张图片吗？')) {
            container.parentNode.removeChild(container);
            // 同步到textarea
            const questionContent = document.getElementById('question-content');
            const editorContent = document.getElementById('editor-content');
            if(editorContent && questionContent) {
                questionContent.value = editorContent.innerHTML;
            }
        }
    });
    
    // 添加点击事件，选中图片
    container.addEventListener('click', function(e) {
        // 移除其他图片的选中状态
        document.querySelectorAll('.embedded-image').forEach(img => {
            img.classList.remove('selected');
        });
        
        // 添加选中状态
        imgElement.classList.add('selected');
        
        // 阻止事件冒泡
        e.stopPropagation();
    });
    
    return container;
};

// 导出到全局作用域，确保函数在任何地方都可用
if (typeof window !== 'undefined') {
    console.log('已将makeImageDraggable函数导出到全局作用域');
}
