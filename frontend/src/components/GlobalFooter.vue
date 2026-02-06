<template>
  <footer class="site-footer">
    <div class="footer-content">
      <p class="copyright">
        &copy; {{ currentYear }} 南京工业大学钢结构教学团队 | 网站制作: 游田 | 
        <a href="https://beian.miit.gov.cn/" target="_blank" rel="noopener">苏ICP备2025209144号-1</a>
      </p>
    </div>
  </footer>
</template>

<script setup>
import { ref } from 'vue'

const currentYear = ref(new Date().getFullYear())
</script>

<style scoped>
.site-footer {
  width: 100%;
  padding: 20px 0;
  background-color: #f5f7fa;
  color: #909399;
  text-align: center;
  border-top: 1px solid #ebeef5;
  font-size: 13px;
  margin-top: auto; /* 配合 flex 布局实现 sticky footer */
}

.footer-content {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 20px;
}

.copyright {
  margin: 5px 0;
}

a {
  color: #909399;
  text-decoration: none;
  transition: color 0.3s;
}

a:hover {
  color: #409eff;
}
</style>
