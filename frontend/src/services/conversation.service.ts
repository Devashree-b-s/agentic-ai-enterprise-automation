import apiClient from './api'
import type { Conversation, ConversationDetail } from '../types/agent.types'

export const conversationService = {
  async list(): Promise<Conversation[]> {
    const response = await apiClient.get<Conversation[]>('/conversations')
    return response.data
  },

  async get(id: number): Promise<ConversationDetail> {
    const response = await apiClient.get<ConversationDetail>(`/conversations/${id}`)
    return response.data
  },

  async create(title?: string): Promise<Conversation> {
    const response = await apiClient.post<Conversation>('/conversations', { title })
    return response.data
  },

  async rename(id: number, title: string): Promise<Conversation> {
    const response = await apiClient.patch<Conversation>(`/conversations/${id}`, { title })
    return response.data
  },

  async delete(id: number): Promise<void> {
    await apiClient.delete(`/conversations/${id}`)
  },
}
