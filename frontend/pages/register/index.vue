<template>
  <v-row>
    <v-col>
      <h1>Registration</h1>
      <p>
        At the moment registration is only possible for
        <a href="https://hpi.de/" target="_blank">HPI</a> students with an HPI
        email address.
      </p>
      <MessageList :messages="errors" />
      <v-form v-model="isFormValid">
        <v-container>
          <v-row>
            <v-col cols="12">
              <v-text-field
                v-model="user.username"
                :rules="[
                  rules.required,
                  rules.minLengthUsername,
                  rules.maxLength,
                  rules.charsUsername,
                ]"
                label="Username"
                required
                class="form-field"
                color="secondary"
              ></v-text-field>
            </v-col>

            <v-col cols="12">
              <v-text-field
                v-model="user.email"
                :rules="[rules.required, rules.email]"
                label="Email"
                required
                class="form-field"
                color="secondary"
              ></v-text-field>
            </v-col>
            <v-col cols="12">
              <v-text-field
                v-model="user.password"
                :append-icon="showPassword ? 'mdi-eye' : 'mdi-eye-off'"
                :rules="[
                  rules.required,
                  rules.minLengthPassword,
                  rules.maxLength,
                  rules.number,
                  rules.uppercase,
                  rules.lowercase,
                ]"
                :type="showPassword ? 'text' : 'password'"
                label="Password"
                class="form-field"
                color="secondary"
                @click:append="showPassword = !showPassword"
              ></v-text-field>
            </v-col>
            <v-btn
              :disabled="!isFormValid || loading"
              :loading="loading"
              color="secondary"
              @click="onSubmit"
            >
              Register
            </v-btn>
          </v-row>
        </v-container>
      </v-form>
    </v-col>
  </v-row>
</template>

<script lang="ts">
import { Vue, Component } from 'nuxt-property-decorator'
import { RegistrationUser } from '../users/user.model'
import UserService from './../../services/UserService'

@Component({ middleware: 'guest', auth: false })
export default class Register extends Vue {
  user: RegistrationUser = {
    username: '',
    email: '',
    password: '',
  }

  errors: string[] = []
  isFormValid = false
  showPassword = false
  loading = false
  rules = {
    required: (value: string) => !!value || 'Required.',
    minLengthPassword: (value: string) =>
      value.length >= 10 || 'At least 10 characters.',
    minLengthUsername: (value: string) =>
      value.length >= 3 || 'At least 3 characters.',
    charsUsername: (value: string) =>
      /^[a-zA-Z][a-zA-Z0-9._-]*$/.test(value) || 'Invalid characters.',
    number: (value: string) => /\d/.test(value) || 'At least one number.',
    lowercase: (value: string) =>
      /[a-z]/.test(value) || 'At least one lower case letter.',
    uppercase: (value: string) =>
      /[A-Z]/.test(value) || 'At least one upper case letter',
    maxLength: (value: string) =>
      value.length <= 100 || 'Maximum 100 characters.',
    email: (value: string) => {
      const pattern = /^[\w.-]*@([\w.-]+\.)?(hpi\.de|hpi\.uni-potsdam\.de)$/
      return pattern.test(value) || 'Invalid email.'
    },
  }

  onSubmit() {
    this.loading = true
    this.errors = []
    UserService.register(this.$axios, this.user)
      .then((_res: any) => {
        this.$router.push('/register/confirm')
      })
      .catch((error) => {
        if (error.response.data.errors) {
          this.errors.push(
            ...Object.values(error.response.data.errors as string)
          )
        } else {
          console.log(error)
        }
        this.loading = false
      })
  }
}
</script>

<style scoped>
.form-field {
  max-width: 300px;
}
</style>
