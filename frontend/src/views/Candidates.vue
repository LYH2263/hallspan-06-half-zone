<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const rows = ref<any[]>([])
const errMsg = ref('')
const okMsg = ref('')
const busy = ref<number | null>(null)

async function load() { rows.value = await api('/candidates') }
onMounted(load)

async function mark(r: any, side: 'left' | 'right' | null) {
  errMsg.value = ''; okMsg.value = ''
  busy.value = r.id
  try {
    const res = await api(`/candidates/${r.id}/side`,
      { method: 'POST', body: JSON.stringify({ side }) })
    const who = side === 'left' ? '左账' : side === 'right' ? '右账' : '未标记（提交时归账）'
    okMsg.value = `${r.name} 已设为${who}；本次提交两本账同成功：左账 ${res.stats.left_seated} 人 / 右账 ${res.stats.right_seated} 人。`
    await load()
  } catch (e: any) {
    // 提交失败：标记与最新方案都不落，名册保持原标记。
    errMsg.value = `标记未保存，三处不动：${e?.message || e}`
  } finally {
    busy.value = null
  }
}
const sideLabel = (s?: string | null) => s === 'left' ? '左账' : s === 'right' ? '右账' : '未标记'
</script>
<template>
  <h1>考生名册</h1>
  <p class="sub">未标记考生在下一次提交里归入且仅归入一本账；改标记即一次两本账同成功/同失败的提交</p>
  <p v-if="errMsg" class="err-banner">{{ errMsg }}</p>
  <p v-if="okMsg" class="ok-banner">{{ okMsg }}</p>
  <div class="hs-clipboard" style="max-width:560px">
    <h2>考生名册 · 左右账标记</h2>
    <div v-for="r in rows" :key="r.id" class="hs-roster-row cand-side-row">
      <div>
        <div>{{ r.name }} <span :class="'mk-badge mk-' + (r.side || 'none')">{{ sideLabel(r.side) }}</span></div>
        <div class="hs-ticket">{{ r.ticket_no }} · 卷{{ r.paper_id }} · 室{{ r.hall_id }}</div>
      </div>
      <div class="mk-btns">
        <button class="mini left" :class="{ on: r.side === 'left' }" :disabled="busy === r.id" @click="mark(r, 'left')">左</button>
        <button class="mini right" :class="{ on: r.side === 'right' }" :disabled="busy === r.id" @click="mark(r, 'right')">右</button>
        <button class="mini none" :class="{ on: !r.side }" :disabled="busy === r.id" @click="mark(r, null)">未</button>
      </div>
    </div>
  </div>
</template>
