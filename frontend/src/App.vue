<template>
  <div id="app-container">
    <div class="main-view">
      <router-view></router-view>
    </div>
    <GlobalFooter />
  </div>
</template>

<script setup>
import GlobalFooter from './components/GlobalFooter.vue'
</script>

<style>
/* 这里可以放全局样式 */
body {
  margin: 0;
  padding: 0;
}

#app-container {
  font-family: 'Helvetica Neue', Helvetica, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', '微软雅黑', Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  color: #2c3e50;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.main-view {
  flex: 1; /* 让主要内容区域占据剩余空间，把页脚推到底部 */
  width: 100%;
}
</style>
