<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const rows = ref<any[]>([])
const draft = ref<Record<number, number>>({})
const errMsg = ref('')
const okMsg = ref('')
const busy = ref<number | null>(null)

async function load() {
  rows.value = await api('/halls')
  draft.value = Object.fromEntries(rows.value.map((r: any) => [r.id, r.split_col]))
}
onMounted(load)

async function saveSplit(h: any) {
  errMsg.value = ''; okMsg.value = ''
  const val = Number(draft.value[h.id])
  if (val === h.split_col) return
  busy.value = h.id
  try {
    const res = await api(`/halls/${h.id}/split`, { method: 'POST', body: JSON.stringify({ split_col: val }) })
    okMsg.value = `分界列已改为 ${res.split_col}，左账 ${res.stats.left_seated} 人 / 右账 ${res.stats.right_seated} 人，新方案已提交（历史方案不回刷）。`
    await load()
  } catch (e: any) {
    errMsg.value = `分界列保存被拒，三处不动：${e?.message || e}`
    draft.value[h.id] = h.split_col  // 回退输入框：分界列未变
  } finally {
    busy.value = null
  }
}
</script>
<template>
  <h1>考室</h1>
  <p class="sub">考室网格、最小曼哈顿间距与左右半场分界列</p>
  <p v-if="errMsg" class="err-banner">{{ errMsg }}</p>
  <p v-if="okMsg" class="ok-banner">{{ okMsg }}</p>
  <div class="card">
    <table>
      <thead><tr><th>编码</th><th>名称</th><th>行</th><th>列</th><th>最小间距</th><th>分界列(1~列-1)</th><th></th></tr></thead>
      <tbody>
        <tr v-for="r in rows" :key="r.id">
          <td>{{ r.code }}</td><td>{{ r.name }}</td><td>{{ r.rows }}</td><td>{{ r.cols }}</td>
          <td>{{ r.min_manhattan }}</td>
          <td>
            <input class="split-input" type="number" min="1" :max="r.cols - 1"
                   v-model.number="draft[r.id]" :disabled="busy === r.id" />
            <span class="muted" style="font-size:.72rem"> 左账列 &lt; 分界列</span>
          </td>
          <td><button class="btn btn-sm" :disabled="busy === r.id || draft[r.id] === r.split_col"
                      @click="saveSplit(r)">提交并重排两本账</button></td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
