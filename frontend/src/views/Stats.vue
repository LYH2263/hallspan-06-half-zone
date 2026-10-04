<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const s = ref<any>({})
onMounted(async () => { s.value = await api('/seating/stats?hall_id=1') })
</script>
<template>
  <h1>统计</h1>
  <p class="sub">排座占用与违规汇总 · 左右两本账与排座图同源</p>
  <div class="card" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:1rem">
    <div><div class="muted">已排座</div><div class="stat">{{ s.seated }}</div></div>
    <div><div class="muted">未排上</div><div class="stat">{{ s.unplaced }}</div></div>
    <div><div class="muted">违规数</div><div class="stat">{{ s.violations }}</div></div>
    <div><div class="muted">座位容量</div><div class="stat">{{ s.capacity }}</div></div>
  </div>
  <div class="card" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:1rem">
    <div>
      <div class="muted">左账已座（列 &lt; {{ s.split_col }}）</div>
      <div class="stat book-left-num">{{ s.left_seated }} <span class="muted stat-sub">/ {{ s.left_capacity }} 座</span></div>
    </div>
    <div>
      <div class="muted">右账已座（列 ≥ {{ s.split_col }}）</div>
      <div class="stat book-right-num">{{ s.right_seated }} <span class="muted stat-sub">/ {{ s.right_capacity }} 座</span></div>
    </div>
    <div>
      <div class="muted">合账人数之差</div>
      <div class="stat" :class="(s.side_diff ?? 0) > 1 ? 'stat-bad' : 'stat-ok'">{{ s.side_diff }}</div>
      <div class="muted stat-sub">{{ (s.side_diff ?? 0) > 1 ? '差 > 1，整场失败' : '差 ≤ 1，均衡达标' }}</div>
    </div>
  </div>
  <p class="muted" style="font-size:.78rem">左账 {{ s.left_seated }} + 右账 {{ s.right_seated }} = 已排座 {{ s.seated }}，与排座图为同一份提交结果。</p>
</template>
