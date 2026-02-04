<template>
    <header class="nav-header">
        <div class="brand">
            <template v-if="showBack">
                <button @click="$emit('back')" class="back-btn">← 返回列表</button>
            </template>
            <template v-else>
                 <span class="logo-icon">📚</span>
            </template>
           
            <h1>{{ title }}</h1>
        </div>
        <div class="user-info">
            <slot name="extra"></slot>
            <span class="welcome" v-if="studentId">{{ studentId }}</span>
            <button @click="$emit('logout')" class="logout-btn">退出</button>
        </div>
    </header>
</template>

<script setup>
defineProps({
    title: {
        type: String,
        default: '在线作业系统'
    },
    studentId: {
        type: String,
        default: ''
    },
    showBack: {
        type: Boolean,
        default: false
    }
})

defineEmits(['logout', 'back'])
</script>

<style scoped>
.nav-header {
    background: #fff;
    height: 60px;
    padding: 0 40px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    position: sticky;
    top: 0;
    z-index: 10;
}

.brand {
    display: flex;
    align-items: center;
    gap: 10px;
}
.brand h1 {
    font-size: 18px;
    margin: 0;
    color: #303133;
    font-weight: 600;
}
.logo-icon {
    font-size: 24px;
}

.user-info {
    display: flex;
    align-items: center;
    gap: 20px;
}
.welcome {
    font-size: 14px;
    color: #606266;
}
.logout-btn {
    border: 1px solid #dcdfe6;
    background: transparent;
    color: #606266;
    padding: 6px 16px;
    border-radius: 20px;
    cursor: pointer;
    font-size: 13px;
    transition: all 0.3s;
}
.logout-btn:hover {
    color: #f56c6c;
    border-color: #fbc4c4;
    background-color: #fef0f0;
}

.back-btn {
    background: none;
    border: 1px solid #dcdfe6;
    padding: 5px 12px;
    border-radius: 4px;
    cursor: pointer;
    color: #606266;
    font-size: 13px;
    margin-right: 10px;
}
.back-btn:hover {
    color: #409eff;
    border-color: #c6e2ff;
}

@media (max-width: 600px) {
    .nav-header {
        padding: 0 20px;
    }
}
</style>