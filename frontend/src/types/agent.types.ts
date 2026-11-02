export interface AgentChatRequest {
  message: string
  conversation_id?: number | null
}

export interface DocumentCitation {
  document_name: string
  chunk_index: number
  total_chunks: number
  department: string
  similarity_score: number
  excerpt: string
}

export interface AgentChatResponse {
  answer: string
  departments_used: string[]
  agents_involved?: string[]
  tools_used: string[]
  success: boolean
  error: string | null
  source_attribution?: 'database' | 'documents' | 'hybrid' | null
  citations?: DocumentCitation[]
  conversation_id?: number | null
}

export interface ChatMessage {
  id: string
  sender: 'user' | 'assistant'
  content: string
  timestamp: string
  departmentsUsed?: string[]
  agentsInvolved?: string[]
  toolsUsed?: string[]
  success?: boolean
  error?: string | null
  status?: 'success' | 'partial' | 'denied' | 'error'
  retryPrompt?: string
  sourceAttribution?: 'database' | 'documents' | 'hybrid' | null
  citations?: DocumentCitation[]
}

export interface QuerySuggestion {
  label: string
  department: 'HR' | 'Sales' | 'Inventory' | 'Analytics' | 'Cross-Dept' | 'Documents' | 'Hybrid'
  query: string
  description?: string
}

export interface Conversation {
  id: number
  title: string
  user_id: number
  message_count: number
  created_at: string
  updated_at: string
}

export interface ConversationMessageRecord {
  id: number
  conversation_id: number
  role: 'user' | 'assistant'
  content: string
  departments_used: string[]
  agents_involved?: string[]
  tools_used: string[]
  source_attribution?: 'database' | 'documents' | 'hybrid' | null
  citations: DocumentCitation[]
  created_at: string
}

export interface ConversationDetail extends Conversation {
  messages: ConversationMessageRecord[]
}
