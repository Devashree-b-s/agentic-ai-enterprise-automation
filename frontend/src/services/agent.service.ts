import type { AgentChatRequest, AgentChatResponse } from '../types/agent.types'
import apiClient from './api'

export const agentService = {
  async chat(message: string, conversationId?: number | null): Promise<AgentChatResponse> {
    const payload: AgentChatRequest = {
      message,
      conversation_id: conversationId ?? null,
    }
    const response = await apiClient.post<AgentChatResponse>('/agents/chat', payload)
    return response.data
  },
}
