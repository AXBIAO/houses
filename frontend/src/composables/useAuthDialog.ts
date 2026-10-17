import { ref } from 'vue'

/** 登录框全站只有一个（挂在 HousesLayout），任何页面都可以通过它唤起。 */
const open = ref(false)

export function useAuthDialog() {
  return {
    open,
    show: () => { open.value = true },
  }
}
