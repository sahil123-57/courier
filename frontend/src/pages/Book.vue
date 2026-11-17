<template>
  <div class="max-w-xl mx-auto p-4 space-y-3">
    <h1 class="text-xl font-semibold">Book a parcel</h1>
    <Input v-model="form.sender_name" label="Sender name" />
    <Input v-model="form.sender_phone" label="Sender phone" />
    <Input v-model="form.sender_address" label="Sender address" />
    <Input v-model="form.origin_city" label="From city" />
    <Input v-model="form.recipient_name" label="Recipient name" />
    <Input v-model="form.recipient_phone" label="Recipient phone" />
    <Input v-model="form.recipient_address" label="Recipient address" />
    <Input v-model="form.destination_city" label="To city" />
    <Input v-model="form.weight_kg" type="number" label="Weight (kg)" />
    <Input v-model="form.service_level" type="select" :options="['Standard', 'Express']" label="Service" />

    <p v-if="price">Price: Rs {{ price }}</p>
    <p v-if="error" class="text-red-600">{{ error }}</p>

    <Button @click="getPrice">Check price</Button>
    <Button variant="solid" :loading="loading" @click="bookAndPay">Book and pay</Button>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Button, Input, call } from 'frappe-ui'

const router = useRouter()
const form = reactive({ service_level: 'Standard' })
const price = ref(null)
const error = ref('')
const loading = ref(false)

// one key per page visit, so a double click books only once
const bookingKey = crypto.randomUUID()

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
    error.value = e.messages?.[0] || 'Could not get price'
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

async function bookAndPay() {
  loading.value = true
  error.value = ''
  try {
    const res = await call('courier.api.book_parcel', {
      data: { ...form, booking_key: bookingKey },
    })
    await loadRazorpay()
    new window.Razorpay({
      key: res.key_id,
      order_id: res.order_id,
      amount: res.amount * 100,
      currency: 'INR',
      name: 'Courier',
      // the real payment confirmation comes from the webhook, not from here
      handler: () => router.push('/track/' + res.parcel),
    }).open()
  } catch (e) {
    error.value = e.messages?.[0] || 'Booking failed'
  }
  loading.value = false
}
</script>
