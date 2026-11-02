import React, { useState, useRef, useEffect, useCallback } from 'react'
import {
  Send,
  Bot,
  User as UserIcon,
  Sparkles,
  Layers,
  Wrench,
  Clock,
  RotateCcw,
  Copy,
  Check,
  Trash2,
  TrendingUp,
  Users,
  Package,
  BarChart3,
  FileText,
  Database,
  Plus,
  MessageSquare,
  Edit2,
  X,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react'
import { agentService } from '../services/agent.service'
import { conversationService } from '../services/conversation.service'
import type {
  ChatMessage,
  Conversation,
  QuerySuggestion,
} from '../types/agent.types'
import { useAuthStore } from '../store/auth.store'
import Card from '../components/common/Card'
import Badge from '../components/common/Badge'
import Button from '../components/common/Button'
import LoadingSpinner from '../components/common/LoadingSpinner'

function getNowTimeString(): string {
  return new Intl.DateTimeFormat('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  }).format(new Date())
}

let messageSequence = 0

function generateMessageId(prefix: string): string {
  messageSequence += 1
  return `${prefix}-${Date.now()}-${messageSequence}`
}

function formatRelativeTime(dateString: string): string {
  try {
    const date = new Date(dateString)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / 60000)
    const diffHours = Math.floor(diffMins / 60)
    const diffDays = Math.floor(diffHours / 24)

    if (diffMins < 1) return 'Just now'
    if (diffMins < 60) return `${diffMins}m ago`
    if (diffHours < 24) return `${diffHours}h ago`
    if (diffDays === 1) return 'Yesterday'
    if (diffDays < 7) return `${diffDays}d ago`
    return new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric' }).format(date)
  } catch {
    return 'Recently'
  }
}

// Enterprise Suggested Queries
const ENTERPRISE_QUERY_SUGGESTIONS: QuerySuggestion[] = [
  {
    label: 'Annual Leave Policy',
    department: 'Documents',
    query: "What is the company's annual leave policy?",
    description: 'Corporate handbook guidelines on annual leave quota and expiration rules',
  },
  {
    label: 'Leave Policy vs Pending',
    department: 'Hybrid',
    query: 'Compare our leave policy with the current pending leave requests.',
    description: 'Hybrid evaluation comparing handbook document quota with live database pending leaves',
  },
  {
    label: 'Active Staff Headcount',
    department: 'HR',
    query: 'How many employees are currently active?',
    description: 'Current active workforce staffing across enterprise departments',
  },
  {
    label: 'Pending Leave Approvals',
    department: 'HR',
    query: 'How many leave requests are pending?',
    description: 'Backlog of staff leave requests awaiting approval',
  },
  {
    label: 'Recognized Sales Revenue',
    department: 'Sales',
    query: 'What is our recognized revenue?',
    description: 'Gross revenue recognized from completed and shipped sales orders',
  },
  {
    label: 'Low-Stock Items',
    department: 'Inventory',
    query: 'Which products are running low?',
    description: 'Physical inventory units at or below safety stock thresholds',
  },
]

export const ChatPage: React.FC = () => {
  const { user } = useAuthStore()

  // Conversations state
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [activeConversationId, setActiveConversationId] = useState<number | null>(null)
  const [isLoadingConversations, setIsLoadingConversations] = useState(true)
  const [sidebarOpen, setSidebarOpen] = useState(true)

  // Editing title state
  const [editingConvId, setEditingConvId] = useState<number | null>(null)
  const [editingTitle, setEditingTitle] = useState('')

  // Messages state
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [inputMessage, setInputMessage] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [copiedId, setCopiedId] = useState<string | null>(null)

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLInputElement>(null)

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  useEffect(() => {
    scrollToBottom()
  }, [messages, scrollToBottom])

  // Load conversations on mount
  const refreshConversations = useCallback(() => {
    conversationService
      .list()
      .then((data) => setConversations(data))
      .catch((err) => console.error('Failed to load conversations:', err))
  }, [])

  useEffect(() => {
    let ignore = false
    conversationService
      .list()
      .then((data) => {
        if (!ignore) setConversations(data)
      })
      .catch((err) => {
        if (!ignore) console.error('Failed to load conversations:', err)
      })
      .finally(() => {
        if (!ignore) setIsLoadingConversations(false)
      })
    return () => {
      ignore = true
    }
  }, [])

  // Load conversation details when activeConversationId changes
  useEffect(() => {
    if (!activeConversationId) {
      return
    }

    let ignore = false
    conversationService
      .get(activeConversationId)
      .then((detail) => {
        if (!ignore) {
          const converted: ChatMessage[] = detail.messages.map((m) => ({
            id: `db-${m.id}`,
            sender: m.role,
            content: m.content,
            timestamp: new Intl.DateTimeFormat('en-US', {
              hour: 'numeric',
              minute: '2-digit',
              hour12: true,
            }).format(new Date(m.created_at)),
            departmentsUsed: m.departments_used,
            toolsUsed: m.tools_used,
            sourceAttribution: m.source_attribution,
            citations: m.citations,
            status: 'success',
          }))
          setMessages(converted)
        }
      })
      .catch((err) => {
        if (!ignore) console.error('Failed to load conversation detail:', err)
      })
      .finally(() => {
        if (!ignore) setIsLoading(false)
      })

    return () => {
      ignore = true
    }
  }, [activeConversationId])

  // Handle New Chat button
  const handleNewChat = () => {
    setActiveConversationId(null)
    setMessages([])
    setInputMessage('')
    textareaRef.current?.focus()
  }

  // Handle Renaming
  const handleStartRename = (conv: Conversation, e: React.MouseEvent) => {
    e.stopPropagation()
    setEditingConvId(conv.id)
    setEditingTitle(conv.title)
  }

  const handleSaveRename = async (convId: number) => {
    if (!editingTitle.trim()) return
    try {
      const updated = await conversationService.rename(convId, editingTitle.trim())
      setConversations((prev) =>
        prev.map((c) => (c.id === convId ? { ...c, title: updated.title } : c))
      )
      setEditingConvId(null)
    } catch (err) {
      console.error('Failed to rename conversation:', err)
    }
  }

  // Handle Deleting
  const handleDeleteConversation = async (convId: number, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!window.confirm('Are you sure you want to delete this conversation?')) return
    try {
      await conversationService.delete(convId)
      setConversations((prev) => prev.filter((c) => c.id !== convId))
      if (activeConversationId === convId) {
        handleNewChat()
      }
    } catch (err) {
      console.error('Failed to delete conversation:', err)
    }
  }

  // Handle Send Message
  const handleSendMessage = async (textToSend?: string) => {
    const text = (textToSend || inputMessage).trim()
    if (!text || isLoading) return

    const userMessageId = generateMessageId('user')
    const userMsg: ChatMessage = {
      id: userMessageId,
      sender: 'user',
      content: text,
      timestamp: getNowTimeString(),
    }

    setMessages((prev) => [...prev, userMsg])
    if (!textToSend) setInputMessage('')
    setIsLoading(true)

    try {
      const res = await agentService.chat(text, activeConversationId)

      const assistantMsg: ChatMessage = {
        id: generateMessageId('assistant'),
        sender: 'assistant',
        content: res.answer,
        timestamp: getNowTimeString(),
        departmentsUsed: res.departments_used,
        agentsInvolved: res.agents_involved || res.departments_used,
        toolsUsed: res.tools_used,
        success: res.success,
        error: res.error,
        status: res.success ? 'success' : 'error',
        sourceAttribution: res.source_attribution,
        citations: res.citations,
        retryPrompt: res.success ? undefined : text,
      }

      setMessages((prev) => [...prev, assistantMsg])

      // If a new conversation was created on the backend, update state and conversation list
      if (res.conversation_id && res.conversation_id !== activeConversationId) {
        setActiveConversationId(res.conversation_id)
      }
      // Refresh conversation list to get latest titles and message counts
      refreshConversations()
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : 'Unknown communication error'
      const errorMsg: ChatMessage = {
        id: generateMessageId('assistant-error'),
        sender: 'assistant',
        content: 'Unable to reach the Agentic Decision Support backend. Please check connectivity.',
        timestamp: getNowTimeString(),
        success: false,
        error: errMsg,
        status: 'error',
        retryPrompt: text,
      }
      setMessages((prev) => [...prev, errorMsg])
    } finally {
      setIsLoading(false)
      textareaRef.current?.focus()
    }
  }

  const handleCopyText = (id: string, text: string) => {
    navigator.clipboard.writeText(text)
    setCopiedId(id)
    setTimeout(() => setCopiedId(null), 2000)
  }

  const getDepartmentBadge = (dept: string) => {
    switch (dept.toLowerCase()) {
      case 'hr':
        return { label: 'HR', color: 'bg-emerald-950/70 border-emerald-500/40 text-emerald-300', icon: Users }
      case 'sales':
        return { label: 'Sales', color: 'bg-sky-950/70 border-sky-500/40 text-sky-300', icon: TrendingUp }
      case 'inventory':
        return { label: 'Inventory', color: 'bg-amber-950/70 border-amber-500/40 text-amber-300', icon: Package }
      case 'analytics':
      case 'cross-dept':
        return { label: 'Analytics', color: 'bg-purple-950/70 border-purple-500/40 text-purple-300', icon: BarChart3 }
      case 'documents':
        return { label: 'Documents', color: 'bg-indigo-950/70 border-indigo-500/40 text-indigo-300', icon: FileText }
      case 'hybrid':
        return { label: 'Hybrid RAG', color: 'bg-cyan-950/70 border-cyan-500/40 text-cyan-300', icon: Layers }
      default:
        return { label: dept, color: 'bg-slate-900 border-slate-700 text-slate-300', icon: Database }
    }
  }

  const activeConv = conversations.find((c) => c.id === activeConversationId)

  return (
    <div className="flex h-[calc(100vh-5.5rem)] gap-3 animate-fade-in">
      {/* 1. Conversations Sidebar */}
      <div
        className={`${
          sidebarOpen ? 'w-72 lg:w-80' : 'w-0 -ml-3'
        } transition-all duration-300 shrink-0 flex flex-col bg-slate-900/90 border border-slate-800 rounded-2xl overflow-hidden shadow-xl`}
      >
        {/* Sidebar Header */}
        <div className="p-3 border-b border-slate-800 flex items-center justify-between bg-slate-950/60">
          <div className="flex items-center gap-2">
            <MessageSquare className="w-4 h-4 text-indigo-400" />
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-300">
              Conversations
            </span>
          </div>
          <Button
            variant="primary"
            size="sm"
            onClick={handleNewChat}
            icon={<Plus className="w-3.5 h-3.5" />}
          >
            New Chat
          </Button>
        </div>

        {/* Conversation List */}
        <div className="flex-1 overflow-y-auto p-2 space-y-1.5 custom-scrollbar">
          {isLoadingConversations && conversations.length === 0 ? (
            <div className="flex items-center justify-center py-8 text-xs text-slate-500">
              <LoadingSpinner size="sm" className="mr-2" /> Loading conversations...
            </div>
          ) : conversations.length === 0 ? (
            <div className="p-4 text-center text-xs text-slate-500">
              No conversations yet. Start a new chat!
            </div>
          ) : (
            conversations.map((conv) => {
              const isActive = conv.id === activeConversationId
              const isEditing = editingConvId === conv.id

              return (
                <div
                  key={conv.id}
                  onClick={() => !isEditing && setActiveConversationId(conv.id)}
                  className={`group relative flex items-center justify-between p-2.5 rounded-xl border transition-all cursor-pointer ${
                    isActive
                      ? 'bg-indigo-950/50 border-indigo-500/50 text-white shadow-sm'
                      : 'bg-slate-950/40 hover:bg-slate-800/60 border-slate-800/80 text-slate-300 hover:text-white'
                  }`}
                >
                  <div className="flex items-center gap-2.5 min-w-0 flex-1">
                    <MessageSquare
                      className={`w-3.5 h-3.5 shrink-0 ${
                        isActive ? 'text-indigo-400' : 'text-slate-500 group-hover:text-slate-400'
                      }`}
                    />
                    {isEditing ? (
                      <div className="flex items-center gap-1 flex-1 mr-1">
                        <input
                          type="text"
                          value={editingTitle}
                          onChange={(e) => setEditingTitle(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') handleSaveRename(conv.id)
                            if (e.key === 'Escape') setEditingConvId(null)
                          }}
                          autoFocus
                          className="w-full px-2 py-0.5 text-xs bg-slate-900 border border-indigo-500 rounded text-white focus:outline-none"
                        />
                        <button
                          type="button"
                          onClick={() => handleSaveRename(conv.id)}
                          className="p-1 hover:text-emerald-400 transition-colors"
                        >
                          <Check className="w-3.5 h-3.5" />
                        </button>
                        <button
                          type="button"
                          onClick={() => setEditingConvId(null)}
                          className="p-1 hover:text-slate-400 transition-colors"
                        >
                          <X className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ) : (
                      <div className="min-w-0 flex-1">
                        <div className="text-xs font-medium truncate">{conv.title}</div>
                        <div className="text-[10px] text-slate-500 mt-0.5">
                          {formatRelativeTime(conv.updated_at)} · {conv.message_count} msgs
                        </div>
                      </div>
                    )}
                  </div>

                  {!isEditing && (
                    <div className="hidden group-hover:flex items-center gap-1 shrink-0 ml-1">
                      <button
                        type="button"
                        onClick={(e) => handleStartRename(conv, e)}
                        className="p-1 hover:text-indigo-300 text-slate-400 transition-colors"
                        title="Rename conversation"
                      >
                        <Edit2 className="w-3 h-3" />
                      </button>
                      <button
                        type="button"
                        onClick={(e) => handleDeleteConversation(conv.id, e)}
                        className="p-1 hover:text-rose-400 text-slate-400 transition-colors"
                        title="Delete conversation"
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>
                    </div>
                  )}
                </div>
              )
            })
          )}
        </div>

        {/* User Session Bar */}
        <div className="p-3 border-t border-slate-800 bg-slate-950/80 text-[11px] text-slate-400 flex items-center justify-between">
          <div className="flex items-center gap-2 truncate">
            <div className="w-6 h-6 rounded-full bg-indigo-950 border border-indigo-500/40 flex items-center justify-center text-indigo-300 font-semibold text-[10px]">
              {user?.role?.[0] || 'U'}
            </div>
            <span className="truncate">{user?.email || 'User'}</span>
          </div>
          <Badge size="sm" variant="neutral">{user?.role || 'Role'}</Badge>
        </div>
      </div>

      {/* Sidebar Toggle Button */}
      <button
        type="button"
        onClick={() => setSidebarOpen((prev) => !prev)}
        className="hidden md:flex items-center justify-center w-5 h-8 my-auto rounded-r-md bg-slate-800/80 hover:bg-slate-700 text-slate-400 hover:text-white transition-colors border-y border-r border-slate-700 shadow-md"
        title={sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'}
      >
        {sidebarOpen ? <ChevronLeft className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
      </button>

      {/* 2. Main Chat Panel */}
      <Card className="flex-1 flex flex-col p-0 border border-slate-800 overflow-hidden shadow-2xl bg-slate-950">
        {/* Top Header */}
        <div className="px-5 py-3.5 border-b border-slate-800 bg-slate-900/90 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-md shadow-indigo-500/20 shrink-0">
              <Bot className="w-5 h-5 text-white" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h1 className="text-sm font-semibold text-white truncate">
                  {activeConv ? activeConv.title : 'New AI Consultation'}
                </h1>
                <Badge size="sm" variant="success">Persistent Memory</Badge>
              </div>
              <p className="text-[11px] text-slate-400 truncate mt-0.5">
                LangGraph Supervisor · Read-Only Tools · Server-Side RBAC Enforced
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <Button
              variant="secondary"
              size="sm"
              onClick={handleNewChat}
              icon={<Plus className="w-3.5 h-3.5" />}
            >
              New Chat
            </Button>
          </div>
        </div>

        {/* Message Thread Area */}
        <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-4">
          {messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center p-6 text-slate-400">
              <div className="w-16 h-16 rounded-2xl bg-indigo-950/40 border border-indigo-500/30 flex items-center justify-center mb-4 text-indigo-400 shadow-xl">
                <Sparkles className="w-8 h-8" />
              </div>
              <h2 className="text-base font-semibold text-white mb-2">
                Enterprise AI Decision Support Assistant
              </h2>
              <p className="text-xs text-slate-400 max-w-md mb-6 leading-relaxed">
                Ask operational questions across HR, Sales, Inventory, and Document Policies.
                Previous messages are securely remembered within each conversation.
              </p>
            </div>
          ) : (
            messages.map((msg) => {
              const isUser = msg.sender === 'user'

              return (
                <div
                  key={msg.id}
                  className={`flex gap-3 max-w-3xl ${
                    isUser ? 'ml-auto flex-row-reverse' : 'mr-auto'
                  }`}
                >
                  {/* Sender Avatar */}
                  <div
                    className={`w-8 h-8 rounded-xl flex items-center justify-center shrink-0 shadow-md ${
                      isUser
                        ? 'bg-indigo-600 text-white'
                        : 'bg-slate-900 border border-slate-700 text-indigo-400'
                    }`}
                  >
                    {isUser ? <UserIcon className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
                  </div>

                  {/* Message Bubble Content */}
                  <div
                    className={`p-4 rounded-2xl text-xs md:text-sm leading-relaxed transition-all shadow-md ${
                      isUser
                        ? 'bg-indigo-600 text-white rounded-tr-xs'
                        : 'bg-slate-900/90 border border-slate-800 text-slate-200 rounded-tl-xs'
                    }`}
                  >
                    {/* Header line inside bubble */}
                    <div className="flex items-center justify-between gap-4 mb-2">
                      <div className="flex items-center gap-1.5">
                        <span className="font-semibold text-[11px] opacity-80">
                          {isUser ? user?.email || 'You' : 'AI Supervisor'}
                        </span>
                        {msg.sourceAttribution && (
                          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] bg-indigo-950/80 border border-indigo-500/30 text-indigo-300">
                            Source: {msg.sourceAttribution}
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-1 text-[10px] text-slate-400">
                        <Clock className="w-3 h-3" />
                        <span>{msg.timestamp}</span>
                        {!isUser && (
                          <button
                            type="button"
                            onClick={() => handleCopyText(msg.id, msg.content)}
                            className="p-1 hover:text-white transition-colors ml-1"
                            title="Copy answer"
                          >
                            {copiedId === msg.id ? (
                              <Check className="w-3 h-3 text-emerald-400" />
                            ) : (
                              <Copy className="w-3 h-3" />
                            )}
                          </button>
                        )}
                      </div>
                    </div>

                    {/* Main Text Content */}
                    <div className="whitespace-pre-wrap font-sans text-xs md:text-sm">
                      {msg.content}
                    </div>

                    {/* Citations Drawer */}
                    {msg.citations && msg.citations.length > 0 && (
                      <div className="mt-3 pt-2.5 border-t border-slate-800 text-[11px] space-y-1.5">
                        <div className="text-slate-400 font-medium flex items-center gap-1">
                          <FileText className="w-3 h-3 text-indigo-400" />
                          <span>Document Citations:</span>
                        </div>
                        <div className="space-y-1 pl-2">
                          {msg.citations.map((c, cIdx) => (
                            <div
                              key={cIdx}
                              className="p-2 rounded bg-slate-950/60 border border-slate-800 text-slate-300 font-mono text-[10px]"
                            >
                              <div className="font-semibold text-indigo-300">
                                {c.document_name} (Chunk {c.chunk_index + 1})
                              </div>
                              <div className="text-slate-400 mt-0.5 italic">
                                &quot;{c.excerpt}&quot;
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Multi-Agent Supervisor Telemetry Footer */}
                    {!isUser && (msg.departmentsUsed || msg.toolsUsed || msg.agentsInvolved) && (
                      <div className="mt-3 pt-2.5 border-t border-slate-800/80 space-y-1 text-[11px]">
                        <div className="flex flex-wrap items-center gap-1.5">
                          <span className="text-[11px] font-medium text-slate-400 mr-1">
                            Coordinating Agents:
                          </span>
                          {(msg.agentsInvolved || msg.departmentsUsed || []).length > 0 ? (
                            (msg.agentsInvolved || msg.departmentsUsed || []).map((agentKey) => {
                              const b = getDepartmentBadge(agentKey)
                              const IconComp = b.icon
                              return (
                                <span
                                  key={agentKey}
                                  className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium border ${b.color}`}
                                >
                                  <IconComp className="w-3 h-3" />
                                  {b.label} Specialist
                                </span>
                              )
                            })
                          ) : (
                            <span className="text-[11px] text-slate-500 italic">
                              Lead Supervisor
                            </span>
                          )}
                        </div>
                        {/* Tools Invoked */}
                        {msg.toolsUsed && msg.toolsUsed.length > 0 && (
                          <div className="flex flex-wrap items-center gap-1.5 pt-0.5">
                            <span className="text-[11px] font-medium text-slate-400 mr-1">
                              Tools:
                            </span>
                            {msg.toolsUsed.map((tool) => (
                              <span
                                key={tool}
                                className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-slate-900 border border-slate-800 font-mono text-[10px] text-indigo-300"
                              >
                                <Wrench className="w-2.5 h-2.5 text-indigo-400" />
                                {tool}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    )}

                    {/* Retry on Error */}
                    {msg.status === 'error' && msg.retryPrompt && (
                      <div className="mt-3 flex justify-end">
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => handleSendMessage(msg.retryPrompt)}
                          disabled={isLoading}
                          icon={<RotateCcw className="w-3.5 h-3.5" />}
                        >
                          Retry Query
                        </Button>
                      </div>
                    )}
                  </div>
                </div>
              )
            })
          )}

          {/* Loading Indicator */}
          {isLoading && (
            <div className="flex gap-3 max-w-2xl mr-auto w-full animate-fade-in">
              <div className="w-8 h-8 rounded-xl bg-slate-900 border border-indigo-500/40 text-indigo-400 flex items-center justify-center shrink-0 shadow-lg">
                <Bot className="w-4 h-4 animate-spin text-indigo-400" />
              </div>
              <div className="p-4 rounded-2xl bg-slate-900/90 border border-indigo-900/40 text-slate-300 rounded-tl-xs text-xs space-y-2 flex-1 shadow-md">
                <div className="flex items-center gap-2 text-indigo-300 font-medium">
                  <LoadingSpinner size="sm" />
                  <span>AI Supervisor evaluating question with persistent memory...</span>
                </div>
                <div className="text-[11px] text-slate-400 pl-6 flex flex-col gap-1">
                  <span>Resolving conversational references &amp; pronouns</span>
                  <span>Executing authorized department tools</span>
                  <span>Synthesizing grounded response</span>
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Suggestion Chips */}
        {messages.length === 0 && (
          <div className="px-4 py-3 border-t border-slate-800 bg-slate-950/70">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-300 mb-2">
              <Sparkles className="w-3.5 h-3.5 text-amber-400" />
              <span>Suggested Queries</span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
              {ENTERPRISE_QUERY_SUGGESTIONS.map((item, idx) => {
                const b = getDepartmentBadge(item.department)
                const IconComp = b.icon
                return (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => handleSendMessage(item.query)}
                    disabled={isLoading}
                    className="flex items-start gap-2.5 p-2 rounded-lg bg-slate-900/70 hover:bg-slate-800/80 border border-slate-800 hover:border-slate-700 text-left transition-all disabled:opacity-50 cursor-pointer group"
                  >
                    <div className={`p-1.5 rounded-md shrink-0 mt-0.5 border ${b.color}`}>
                      <IconComp className="w-3.5 h-3.5" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="text-xs font-semibold text-slate-200 group-hover:text-indigo-300 transition-colors truncate">
                        {item.query}
                      </div>
                      <div className="text-[10px] text-slate-400 truncate mt-0.5">
                        {item.description}
                      </div>
                    </div>
                  </button>
                )
              })}
            </div>
          </div>
        )}

        {/* Input Form */}
        <div className="p-4 border-t border-slate-800 bg-slate-900/90">
          <form
            onSubmit={(e) => {
              e.preventDefault()
              handleSendMessage()
            }}
            className="flex items-center gap-2"
          >
            <div className="relative flex-1">
              <input
                ref={textareaRef}
                type="text"
                value={inputMessage}
                onChange={(e) => setInputMessage(e.target.value)}
                placeholder="Ask an operational question or follow-up..."
                disabled={isLoading}
                className="w-full px-4 py-2.5 bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-xl text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 transition-colors disabled:opacity-50"
              />
            </div>
            <Button
              type="submit"
              variant="primary"
              size="md"
              disabled={!inputMessage.trim() || isLoading}
              icon={<Send className="w-4 h-4" />}
            >
              Send
            </Button>
          </form>
          <div className="flex flex-wrap items-center justify-between gap-1 text-[10px] text-slate-500 mt-2 px-1">
            <span>Conversations isolated by user · History stored securely in SQLite</span>
            <span className="text-slate-400">Context window: 10 turns</span>
          </div>
        </div>
      </Card>
    </div>
  )
}

export default ChatPage
