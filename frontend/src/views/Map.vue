<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'
const data = ref<any>(null)
const candidates = ref<any[]>([])
const violKeys = ref<Set<string>>(new Set())
const errMsg = ref('')
const loading = ref(false)

async function run() {
  loading.value = true
  errMsg.value = ''
  try {
    // 提交瞬间两本账切开；图、左右人数、统计都来自这同一份响应。
    const d = await api('/seating/run?hall_id=1', { method: 'POST' })
    data.value = d
    try {
      const v = await api('/seating/violations?hall_id=1')
      const keys = new Set<string>()
      for (const x of v.violations || []) {
        if (x.a_id != null) keys.add(String(x.a_id))
        if (x.b_id != null) keys.add(String(x.b_id))
      }
      violKeys.value = keys
    } catch { violKeys.value = new Set() }
  } catch (e: any) {
    // 失败：不增方案，保留上一张成功排座图，仅提示原因。
    errMsg.value = e?.message || '本次排座提交失败'
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  candidates.value = await api('/candidates')
  // 先读最新方案（历史最新，不自动重排），没有再触发一次提交。
  try {
    data.value = await api('/seating/latest?hall_id=1')
    if (!data.value?.id) await run()
  } catch {
    await run()
  }
})

const gridStyle = computed(() => data.value ? ({ gridTemplateColumns: `repeat(${data.value.cols}, 72px)` }) : {})
const cells = computed(() => {
  if (!data.value) return []
  const map = new Map<string, any>()
  for (const a of data.value.assignments || []) map.set(a.row + ',' + a.col, a)
  const out: any[] = []
  for (let r = 0; r < data.value.rows; r++) {
    for (let c = 0; c < data.value.cols; c++) {
      out.push(map.get(r + ',' + c) || { empty: true, row: r, col: c })
    }
  }
  return out
})
function isViol(cell: any) {
  if (cell.empty) return false
  const id = cell.candidate_id ?? cell.id
  return id != null && violKeys.value.has(String(id))
}
function paperClass(pid: number) {
  return pid % 2 === 0 ? 'b' : 'a'
}
const sideLabel = (s?: string | null) => s === 'left' ? '左' : s === 'right' ? '右' : '—'
</script>
<template>
  <h1>考场课桌网格 · 左右两本账</h1>
  <p class="sub">分界列在提交排座瞬间切开两本账 · 排座图 / 左账人数 / 右账人数同源于一次提交</p>
  <div class="bar">
    <button class="btn" :disabled="loading" @click="run">{{ loading ? '排座中…' : '重新排座（提交两本账）' }}</button>
    <span v-if="data?.stats" class="books">
      <span class="book-pill left">左账 {{ data.stats.left_seated }} 人 / {{ data.stats.left_capacity }} 座</span>
      <span class="book-pill right">右账 {{ data.stats.right_seated }} 人 / {{ data.stats.right_capacity }} 座</span>
      <span class="muted">合账差 {{ data.stats.side_diff }}（&gt;1 整场失败）· 分界列 {{ data.split_col }}</span>
    </span>
  </div>
  <p v-if="errMsg" class="err-banner">本次提交失败，未新增方案，分界列 / 左右标记 / 最新方案三处不动：{{ errMsg }}</p>
  <div class="hs-classroom" style="margin-top:0.85rem">
    <aside class="hs-clipboard">
      <h2>考生名册</h2>
      <div v-for="c in candidates" :key="c.id" class="hs-roster-row">
        <div>
          <div>{{ c.name }}</div>
          <div class="hs-ticket">{{ c.ticket_no }}</div>
        </div>
        <div>卷{{ c.paper_id }} · <span :class="'mk-' + (c.side || 'none')">{{ sideLabel(c.side) }}</span></div>
      </div>
    </aside>
    <div class="hs-desk-stage" v-if="data">
      <div class="hs-grid-board" :style="gridStyle">
        <div
          v-for="(cell,i) in cells" :key="i"
          class="hs-desk"
          :class="{ empty: cell.empty, 'hs-viol': isViol(cell),
                    'book-left': !cell.empty && cell.side === 'left',
                    'book-right': !cell.empty && cell.side === 'right',
                    'split-line': cell.col === data.split_col }"
        >
          <template v-if="!cell.empty">
            <span class="hs-paper-tag" :class="paperClass(cell.paper_id)">卷{{ cell.paper_id }}</span>
            <div>{{ cell.name }}</div>
            <div class="hs-side-tag">{{ cell.side === 'left' ? '左账' : '右账' }}</div>
          </template>
          <template v-else>·</template>
        </div>
      </div>
    </div>
  </div>
</template>
