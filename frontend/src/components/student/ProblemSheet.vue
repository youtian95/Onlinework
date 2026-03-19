<template>
  <section ref="sheetRootRef" class="problem-sheet card-shell">
    <template v-if="teamworkEnabled && renderSequence.length">
      <template v-for="segment in renderSequence" :key="segment.key">
        <div
          v-if="segment.type === 'plain'"
          class="problem-content markdown-body"
          v-html="segment.html"
        ></div>

        <article
          v-else-if="segment.type === 'subproblem' && blockOf(segment.subproblem_no)"
          class="subproblem-card card-shell"
          :class="getCardClass(blockOf(segment.subproblem_no))"
        >
          <div class="subproblem-header-row">
            <div class="subproblem-main">
              <span class="subproblem-index">子题 {{ segment.subproblem_no }}</span>
              <span
                class="meta-chip"
                :class="claimChipClass(segment.subproblem_no)"
              >
                {{ claimText(segment.subproblem_no) }}
              </span>
            </div>
            <div class="subproblem-actions">
              <button type="button" class="collapse-btn" @click="emit('toggle-subproblem', segment.subproblem_no)">
                {{ isOpen(segment.subproblem_no) ? '收起内容' : '展开内容' }}
              </button>
              <button
                v-if="token"
                type="button"
                class="claim-btn"
                :class="{ secondary: getClaimKind(blockOf(segment.subproblem_no)) !== 'primary' }"
                :disabled="isClaimDisabled(blockOf(segment.subproblem_no))"
                @click="emit('claim-subproblem', segment.subproblem_no)"
              >
                {{ getClaimText(blockOf(segment.subproblem_no)) }}
              </button>
            </div>
          </div>

          <div
            v-show="isOpen(segment.subproblem_no)"
            class="subproblem-body markdown-body"
            v-html="blockOf(segment.subproblem_no).html"
          ></div>
        </article>
      </template>
    </template>

    <template v-else>
      <div
        v-if="renderedContent"
        class="problem-content markdown-body"
        v-html="renderedContent"
      ></div>

      <section v-if="teamworkEnabled && renderedSubproblems.length" class="subproblem-section">
        <article
          v-for="block in renderedSubproblems"
          :key="block.subproblem_no"
          class="subproblem-card card-shell"
          :class="getCardClass(block)"
        >
          <div class="subproblem-header-row">
            <div class="subproblem-main">
              <span class="subproblem-index">子题 {{ block.subproblem_no }}</span>
              <span
                class="meta-chip"
                :class="claimChipClass(block.subproblem_no)"
              >
                {{ claimText(block.subproblem_no) }}
              </span>
            </div>
            <div class="subproblem-actions">
              <button type="button" class="collapse-btn" @click="emit('toggle-subproblem', block.subproblem_no)">
                {{ isOpen(block.subproblem_no) ? '收起内容' : '展开内容' }}
              </button>
              <button
                v-if="token"
                type="button"
                class="claim-btn"
                :class="{ secondary: getClaimKind(block) !== 'primary' }"
                :disabled="isClaimDisabled(block)"
                @click="emit('claim-subproblem', block.subproblem_no)"
              >
                {{ getClaimText(block) }}
              </button>
            </div>
          </div>

          <div
            v-show="isOpen(block.subproblem_no)"
            class="subproblem-body markdown-body"
            v-html="block.html"
          ></div>
        </article>
      </section>
    </template>
  </section>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  teamworkEnabled: {
    type: Boolean,
    default: false,
  },
  renderSequence: {
    type: Array,
    default: () => [],
  },
  renderedContent: {
    type: String,
    default: '',
  },
  renderedSubproblems: {
    type: Array,
    default: () => [],
  },
  subproblemMap: {
    type: Object,
    default: () => ({}),
  },
  studentId: {
    type: String,
    default: '',
  },
  token: {
    type: String,
    default: '',
  },
  isSubproblemOpen: {
    type: Function,
    default: () => false,
  },
  getSubproblemCardClass: {
    type: Function,
    default: () => ({}),
  },
  getSubproblemStateText: {
    type: Function,
    default: () => '',
  },
  getClaimButtonKind: {
    type: Function,
    default: () => 'primary',
  },
  isClaimButtonDisabled: {
    type: Function,
    default: () => true,
  },
  getClaimButtonText: {
    type: Function,
    default: () => '',
  },
  getClaimForSubproblem: {
    type: Function,
    default: () => null,
  },
})

const emit = defineEmits(['toggle-subproblem', 'claim-subproblem'])
const sheetRootRef = ref(null)

const blockOf = (subproblemNo) => props.subproblemMap?.[subproblemNo] || null
const isOpen = (subproblemNo) => props.isSubproblemOpen(subproblemNo)
const getCardClass = (block) => props.getSubproblemCardClass(block)
const getClaimKind = (block) => props.getClaimButtonKind(block)
const isClaimDisabled = (block) => props.isClaimButtonDisabled(block)
const getClaimText = (block) => props.getClaimButtonText(block)
const claimOf = (subproblemNo) => props.getClaimForSubproblem(subproblemNo)

const claimText = (subproblemNo) => {
  const claim = claimOf(subproblemNo)
  if (!claim) {
    return '尚未认领'
  }
  return `${claim.name || claim.student_id} 负责`
}

const claimChipClass = (subproblemNo) => {
  const claim = claimOf(subproblemNo)
  if (!claim) {
    return 'available'
  }
  if (claim.student_id === props.studentId) {
    return 'mine'
  }
  return 'teammate'
}

defineExpose({
  getRootEl: () => sheetRootRef.value,
})
</script>

<style scoped>
.card-shell {
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.96) 0%, #ffffff 100%);
  border: 1px solid #e5ecf3;
  border-radius: 24px;
  box-shadow: 0 20px 45px rgba(15, 23, 42, 0.06);
}

.claim-btn {
  border: none;
  border-radius: 999px;
  padding: 10px 16px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 700;
  transition: transform 0.12s ease, box-shadow 0.2s ease, filter 0.2s ease;
  color: #fff;
  background: linear-gradient(135deg, #1d4ed8 0%, #2563eb 100%);
  box-shadow: 0 10px 24px rgba(37, 99, 235, 0.22);
}

.claim-btn:hover:not(:disabled) {
  transform: translateY(-1px);
}

.claim-btn:disabled {
  cursor: not-allowed;
  box-shadow: none;
  opacity: 0.65;
}

.claim-btn.secondary {
  background: linear-gradient(135deg, #475569 0%, #64748b 100%);
  box-shadow: 0 10px 24px rgba(71, 85, 105, 0.18);
}

.problem-sheet {
  margin-bottom: 20px;
  padding: 22px;
  display: grid;
  gap: 16px;
}

.problem-content {
  padding: 4px 8px;
}

.subproblem-section {
  display: grid;
  gap: 16px;
}

.subproblem-card {
  padding: 20px 22px;
}

.subproblem-card.mine {
  border-color: #93c5fd;
  background: linear-gradient(180deg, #f8fbff 0%, #ffffff 100%);
}

.subproblem-card.locked {
  background: linear-gradient(180deg, #fbfdff 0%, #f8fafc 100%);
}

.subproblem-header-row {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  padding-bottom: 10px;
}

.subproblem-main {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}

.subproblem-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}

.collapse-btn {
  border: 1px solid #cbd5e1;
  border-radius: 999px;
  padding: 8px 14px;
  background: #ffffff;
  color: #334155;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
}

.collapse-btn:hover {
  background: #f8fafc;
  border-color: #94a3b8;
}

.subproblem-index {
  font-size: 12px;
  color: #2563eb;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  border-radius: 999px;
  padding: 6px 10px;
  font-weight: 700;
}

.meta-chip {
  border-radius: 999px;
  padding: 6px 11px;
  font-size: 13px;
  font-weight: 600;
}

.meta-chip.mine {
  color: #1d4ed8;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
}

.meta-chip.teammate {
  color: #7c2d12;
  background: #fff7ed;
  border: 1px solid #fed7aa;
}

.meta-chip.available {
  color: #166534;
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
}

.meta-chip.neutral {
  color: #475569;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
}

.subproblem-body {
  border-top: 1px solid #e2e8f0;
  padding-top: 18px;
}

@media (max-width: 840px) {
  .subproblem-header-row {
    flex-direction: column;
    align-items: flex-start;
  }

  .subproblem-actions {
    width: 100%;
  }
}
</style>
