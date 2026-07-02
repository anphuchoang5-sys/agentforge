import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

/**
 * 合并 CSS 类名，使用 tailwind-merge 解决 Tailwind 冲突
 * shadcn/ui 标准工具函数
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
