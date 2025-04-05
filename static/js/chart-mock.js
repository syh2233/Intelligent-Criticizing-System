/**
 * Chart.js 模拟文件
 * 当无法加载正常的Chart.js库时，提供基本的替代功能
 */

// 创建模拟Chart对象
window.Chart = class Chart {
  constructor(ctx, config) {
    this.ctx = ctx;
    this.config = config;
    this.type = config.type;
    this.data = config.data;
    this.options = config.options;
    
    console.log('使用Chart模拟对象创建图表', this.type);
    this._render();
  }
  
  // 简单渲染方法
  _render() {
    if (!this.ctx) return;
    
    const ctx = this.ctx;
    const canvas = ctx.canvas;
    const width = canvas.width;
    const height = canvas.height;
    
    // 清空画布
    ctx.clearRect(0, 0, width, height);
    
    // 绘制背景
    ctx.fillStyle = '#f9f9f9';
    ctx.fillRect(0, 0, width, height);
    
    // 绘制边框
    ctx.strokeStyle = '#ddd';
    ctx.lineWidth = 1;
    ctx.strokeRect(0, 0, width, height);
    
    // 显示提示文本
    ctx.fillStyle = '#666';
    ctx.font = '14px Arial';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('图表加载失败', width / 2, height / 2 - 20);
    ctx.fillText('请检查网络连接并刷新页面', width / 2, height / 2 + 20);
  }
  
  // 提供需要的方法接口
  update() {
    console.log('Chart模拟对象：update');
    this._render();
  }
  
  destroy() {
    console.log('Chart模拟对象：destroy');
    if (this.ctx) {
      const canvas = this.ctx.canvas;
      this.ctx.clearRect(0, 0, canvas.width, canvas.height);
    }
  }
  
  // 静态方法
  static register() {
    console.log('Chart模拟对象：register');
  }
};

console.log('Chart.js 模拟库已加载'); 