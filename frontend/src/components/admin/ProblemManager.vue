<template>
  <div>
    <div class="content-wrapper full-width-layout">
        <ProblemUpload 
            :adminToken="adminToken" 
            @logout="$emit('logout')" 
            @uploaded="refreshList" 
        />
        
        <AdminProblemList 
            ref="problemListRef" 
            :adminToken="adminToken" 
            @logout="$emit('logout')" 
        />
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import ProblemUpload from './ProblemUpload.vue'
import AdminProblemList from './AdminProblemList.vue'

const props = defineProps({
    adminToken: String
})

const emit = defineEmits(['logout'])

const problemListRef = ref(null)

const refreshList = () => {
    if (problemListRef.value) {
        problemListRef.value.fetchAdminProblems()
    }
}
</script>

<style scoped>
.content-wrapper {
    max-width: 1200px;
    margin: 0 auto;
    padding: 0 20px;
}
.full-width-layout {
    display: block;
}
</style>