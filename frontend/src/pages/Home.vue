<template>
  <div class="mx-auto max-w-2xl p-4">
    <div class="mb-4 flex items-center justify-between print:hidden">
      <h1 class="text-xl font-semibold">Courier</h1>
      <div class="flex gap-2">
        <Button @click="showList">My parcels</Button>
        <Button variant="solid" @click="showBook">Book a parcel</Button>
      </div>
    </div>

    <p v-if="error" class="mb-3 rounded bg-[#fef2f2] p-2 text-[#b91c1c] print:hidden">{{ error }}</p>

    <div v-if="view === 'list'">
      <p v-if="!parcels.length" class="text-ink-gray-5">No parcels yet.</p>
      <div v-for="p in parcels" :key="p.name" class="mb-2 cursor-pointer rounded border p-3" @click="openTrack(p.name)">
        <div class="font-medium">{{ p.name }}: {{ p.recipient_name }}, {{ p.destination_city }}<span v-if="p.is_return"> (return)</span></div>
        <div class="mb-2 text-sm text-ink-gray-5">{{ p.status }}</div>
        <div class="flex gap-2">
          <Button @click.stop="openTrack(p.name)">Track</Button>
          <Button v-if="p.payment_status !== 'Unpaid'" @click.stop="openLabel(p.name)">Label</Button>
        </div>
      </div>
    </div>

    <div v-if="view === 'book'">
      <h2 class="mb-2 text-lg font-medium">Book a parcel</h2>
      <label v-for="f in fields" :key="f[0]" class="mb-2 block">
        <span class="text-sm">{{ f[1] }}</span>
        <input v-model="form[f[0]]" class="w-full rounded border border-[#cccccc] px-2 py-1" />
      </label>
      <label class="mb-2 block">
        <span class="text-sm">Weight (kg)</span>
        <input v-model="form.weight_kg" type="number" min="0" step="0.1" class="w-full rounded border border-[#cccccc] px-2 py-1" />
      </label>
      <label class="mb-3 block">
        <span class="text-sm">Service</span>
        <select v-model="form.service_level" class="w-full rounded border border-[#cccccc] px-2 py-1">
          <option>Standard</option>
          <option>Express</option>
        </select>
      </label>

      <p v-if="price !== null" class="mb-3">Price: Rs {{ price }}</p>
      <div class="flex gap-2">
        <Button @click="getPrice">Check price</Button>
        <Button variant="solid" :loading="busy" @click="book">Book and pay</Button>
      </div>

      <div v-if="pay && !pay.key_id" class="mt-4 rounded border p-3">
        <p class="mb-2 text-sm">
          Parcel {{ pay.parcel }} is booked. Razorpay keys are not set on this site (development mode), so the
          payment can be simulated instead.
        </p>
        <Button variant="solid" @click="simulate">Simulate payment</Button>
      </div>
    </div>

    <div v-if="view === 'track' && info">
      <h2 class="text-lg font-medium">{{ info.parcel }}</h2>
      <p class="mb-3">Status: {{ info.status }}</p>
      <p v-if="info.status === 'Unpaid'" class="mb-3 text-sm text-ink-gray-5">Waiting for payment confirmation...</p>
      <ul class="mb-4 border-l-2 pl-4">
        <li v-for="e in info.events" :key="e.creation" class="mb-2">
          <div>{{ e.status }}<span v-if="e.hub"> ({{ e.hub }})</span></div>
          <div class="text-sm text-ink-gray-5">{{ e.creation }}</div>
        </li>
      </ul>
      <div class="flex gap-2">
        <Button v-if="info.status === 'Delivered'" @click="startReturn">Return this parcel</Button>
        <Button v-if="info.status !== 'Unpaid'" @click="openLabel(info.parcel)">Label</Button>
      </div>
    </div>

    <div v-if="view === 'label' && label">
      <div class="border-2 border-black p-4">
        <div class="text-lg font-bold">{{ label.parcel }}</div>
        <canvas ref="qr"></canvas>
        <div class="mt-2"><b>From:</b> {{ label.sender.filter(Boolean).join(', ') }}</div>
        <div><b>To:</b> {{ label.recipient.filter(Boolean).join(', ') }}</div>
        <div>{{ label.weight_kg }} kg, {{ label.service_level }}</div>
      </div>
      <div class="mt-3 flex gap-2 print:hidden">
        <Button variant="solid" @click="printLabel">Print</Button>
        <Button @click="openTrack(label.parcel)">Back to tracking</Button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { nextTick, onMounted, onUnmounted, reactive, ref } from 'vue'
import { Button, call, createResource } from 'frappe-ui'
import QRCode from 'qrcode'

const fields = [
  ['sender_name', 'Sender name'],
  ['sender_phone', 'Sender phone'],
  ['sender_address', 'Sender address'],
  ['origin_city', 'From city'],
  ['recipient_name', 'Recipient name'],
  ['recipient_phone', 'Recipient phone'],
  ['recipient_address', 'Recipient address'],
  ['destination_city', 'To city'],
]

const view = ref('list')
const error = ref('')
const busy = ref(false)
const parcels = ref([])
const info = ref(null)
const label = ref(null)
const price = ref(null)
const pay = ref(null)
const qr = ref(null)
const form = reactive({ service_level: 'Standard' })

const bookingKey = (window.crypto && crypto.randomUUID) ? crypto.randomUUID() : String(Date.now()) + Math.random()

let timer = null

function message(e) {
  return (e.messages && e.messages[0]) || e.message || 'Something went wrong. Are you logged in?'
}

async function showList() {
  view.value = 'list'
  error.value = ''
  try {
    parcels.value = await call('courier.api.my_parcels')
  } catch (e) {
    error.value = message(e)
  }
}

function showBook() {
  view.value = 'book'
  error.value = ''
  pay.value = null
}

async function getPrice() {
  error.value = ''
  try {
    price.value = await call('courier.api.get_quote', {
      origin_city: form.origin_city,
      destination_city: form.destination_city,
      service_level: form.service_level,
      weight_kg: form.weight_kg,
    })
  } catch (e) {
    error.value = message(e)
  }
}

function loadRazorpay() {
  return new Promise((resolve) => {
    if (window.Razorpay) return resolve()
    const s = document.createElement('script')
    s.src = 'https://checkout.razorpay.com/v1/checkout.js'
    s.onload = resolve
    document.body.appendChild(s)
  })
}

async function book() {
  busy.value = true
  error.value = ''
  try {
    const res = await call('courier.api.book_parcel', { data: { ...form, booking_key: bookingKey } })
    pay.value = res
    if (res.key_id) {
      await loadRazorpay()
      new window.Razorpay({
        key: res.key_id,
        order_id: res.order_id,
        amount: res.amount * 100,
        currency: 'INR',
        name: 'Courier',
        handler: (response) => confirmPayment(response, res.parcel),
      }).open()
    }
  } catch (e) {
    error.value = message(e)
  }
  busy.value = false
}

function confirmPayment(response, parcel) {
  createResource({
    url: '/razorpay-api/success-handler',
    auto: true,
    makeParams() {
      return {
        order_id: response.razorpay_order_id,
        payment_id: response.razorpay_payment_id,
        signature: response.razorpay_signature,
      }
    },
    onSuccess() {
      openTrack(parcel)
    },
    onError(e) {
      error.value = message(e)
    },
  })
}

async function simulate() {
  error.value = ''
  try {
    await call('courier.api.dev_simulate_payment', { name: pay.value.parcel })
    openTrack(pay.value.parcel)
  } catch (e) {
    error.value = message(e)
  }
}

async function loadInfo(name) {
  try {
    info.value = await call('courier.api.track_parcel', { name })
  } catch (e) {
    error.value = message(e)
  }
}

async function openTrack(name) {
  view.value = 'track'
  error.value = ''
  info.value = null
  await loadInfo(name)
}

async function startReturn() {
  error.value = ''
  try {
    const returnParcel = await call('courier.api.raise_return', { name: info.value.parcel })
    await openTrack(returnParcel)
  } catch (e) {
    error.value = message(e)
  }
}

async function openLabel(name) {
  error.value = ''
  try {
    label.value = await call('courier.api.get_label', { name })
    view.value = 'label'
    await nextTick()
    QRCode.toCanvas(qr.value, label.value.token, { width: 220 })
  } catch (e) {
    error.value = message(e)
  }
}

function printLabel() {
  window.print()
}

onMounted(() => {
  showList()
  timer = setInterval(() => {
    if (view.value === 'track' && info.value) loadInfo(info.value.parcel)
  }, 8000)
})

onUnmounted(() => clearInterval(timer))
</script>
