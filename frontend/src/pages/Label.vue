<template>
  <div class="max-w-md mx-auto p-4">
    <div v-if="label.data" class="border-2 border-black p-4">
      <div class="text-lg font-bold">{{ label.data.parcel }}</div>
      <canvas ref="qr"></canvas>
      <div class="mt-2"><b>From:</b> {{ label.data.sender.filter(Boolean).join(', ') }}</div>
      <div><b>To:</b> {{ label.data.recipient.filter(Boolean).join(', ') }}</div>
      <div>{{ label.data.weight_kg }} kg, {{ label.data.service_level }}</div>
    </div>
    <p v-if="label.error" class="text-red-600">Label is not available yet</p>
    <Button class="mt-3 print:hidden" @click="print">Print</Button>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import QRCode from 'qrcode'
import { Button, createResource } from 'frappe-ui'

const props = defineProps({ name: String })
const qr = ref(null)

const label = createResource({ url: 'courier.api.get_label', params: { name: props.name }, auto: true })

// draw the barcode once the label has loaded and the canvas exists
watch(
  () => label.data,
  async (data) => {
    if (!data) return
    await Promise.resolve()
    setTimeout(() => QRCode.toCanvas(qr.value, data.token, { width: 200 }), 0)
  }
)

function print() {
  window.print()
}
</script>
