---
name: backend-patterns
description: Advanced backend architecture patterns, API design, database optimization, and server-side best practices for Node.js/Express with TypeScript. Use this skill whenever the user mentions API routes, Express middleware, Drizzle ORM, SQLite, JWT auth, rate limiting, background jobs, error handling, service layers, repository patterns, schema validation, circuit breakers, structured logging, or any server-side architecture concern — even if they don't say "backend patterns" explicitly. Always activate for B2B system design, automate.dev stack work, or any discussion touching Node.js + TypeScript production patterns. Also trigger when reviewing auth code, database queries, or resilience patterns.
---

# Backend Development Patterns — v2 (March 2026)

Stack target: **TypeScript · Node.js · Express 5 · Drizzle ORM · SQLite (WAL) · Zod v4**

> ⚠️ **RS256-ONLY POLICY**: Never use HS256 in production. All JWT examples use asymmetric RS256.

---

## 1. 3-Tier Architecture (Project Structure)

```
src/
├── entry-points/       # HTTP controllers — req/res objects STOP HERE
│   └── api/
├── domain/             # Business logic — DTOs, services, pure logic
│   └── features/
└── data-access/        # DB calls, repositories — Drizzle adapters
    └── repositories/
```

**Principle**: Web objects (`req`, `res`) never leak into domain or data-access layers.
Domain layer is testable from CLI, queues, and tests — not just HTTP.

---

## 2. Zod Schema-First Validation (Single Source of Truth)

```typescript
import { z } from 'zod'

// ✅ Schema is the SINGLE source of truth for types + runtime validation
export const CreateClientSchema = z.object({
  name:     z.string().min(2).max(100).trim(),
  email:    z.string().max(254).email(),  // max before regex → ReDoS prevention
  budget:   z.number().positive().max(1_000_000),
  plan:     z.enum(['starter', 'pro', 'enterprise']),
  apiKey:   z.string().min(32).optional(), // BYOK — client supplies own key
})

// Infer TypeScript type from schema — no duplication
export type CreateClientDto = z.infer<typeof CreateClientSchema>

// ✅ safeParse → no throw, discriminated union result
export function validateBody<T>(schema: z.ZodSchema<T>, body: unknown):
  { success: true; data: T } | { success: false; error: z.ZodError } {
  return schema.safeParse(body)
}

// Express middleware factory
export function zodMiddleware<T>(schema: z.ZodSchema<T>) {
  return (req: Request, res: Response, next: NextFunction) => {
    const result = schema.safeParse(req.body)
    if (!result.success) {
      return res.status(400).json({
        error: 'Validation failed',
        // ⚠️ ATENCIÓN: strip sensitive field names from errors in prod
        issues: result.error.issues.map(i => ({ path: i.path, message: i.message }))
      })
    }
    req.body = result.data  // Overwrite with sanitized, typed data
    next()
  }
}
```

---

## 3. Drizzle ORM + SQLite (WAL Mode)

```typescript
// db/connection.ts
import Database from 'better-sqlite3'
import { drizzle } from 'drizzle-orm/better-sqlite3'
import * as schema from './schema'

const sqlite = new Database('./data/app.db')

// ✅ WAL mode — critical for concurrent reads + writes in production
sqlite.pragma('journal_mode = WAL')
sqlite.pragma('foreign_keys = ON')
sqlite.pragma('busy_timeout = 5000')

export const db = drizzle(sqlite, { schema })

// db/schema.ts
import { integer, sqliteTable, text, real } from 'drizzle-orm/sqlite-core'

export const clients = sqliteTable('clients', {
  id:        integer('id', { mode: 'number' }).primaryKey({ autoIncrement: true }),
  name:      text('name').notNull(),
  email:     text('email').notNull().unique(),
  plan:      text('plan', { enum: ['starter', 'pro', 'enterprise'] }).notNull(),
  // BYOK: encrypted with client's own key — never stored plaintext
  apiKeyEnc: text('api_key_enc'),
  createdAt: integer('created_at', { mode: 'timestamp' })
               .$defaultFn(() => new Date()),
})

export type Client = typeof clients.$inferSelect
export type NewClient = typeof clients.$inferInsert
```

### Repository Pattern with Drizzle

```typescript
// data-access/repositories/client.repository.ts
import { db } from '../connection'
import { clients, type Client, type NewClient } from '../schema'
import { eq, like, inArray, sql } from 'drizzle-orm'

export class ClientRepository {
  async findAll(filters?: { plan?: string; search?: string }): Promise<Client[]> {
    let query = db.select().from(clients).$dynamic()

    // ✅ Drizzle parameterizes automatically — no string concatenation ever
    if (filters?.plan) {
      query = query.where(eq(clients.plan, filters.plan))
    }
    if (filters?.search) {
      query = query.where(like(clients.name, `%${filters.search}%`))
    }
    return query
  }

  async findById(id: number): Promise<Client | undefined> {
    const [row] = await db.select().from(clients).where(eq(clients.id, id)).limit(1)
    return row
  }

  async create(data: NewClient): Promise<Client> {
    const [row] = await db.insert(clients).values(data).returning()
    return row
  }

  // ✅ Drizzle transactions — ACID guaranteed
  async createWithAudit(data: NewClient, auditEntry: unknown): Promise<Client> {
    return db.transaction(async (tx) => {
      const [client] = await tx.insert(clients).values(data).returning()
      // ⚠️ ATENCIÓN: audit insert failure rolls back client insert automatically
      await tx.insert(auditLog).values({ entityId: client.id, ...auditEntry })
      return client
    })
  }

  // ✅ N+1 prevention — batch fetch
  async findByIds(ids: number[]): Promise<Client[]> {
    if (ids.length === 0) return []
    return db.select().from(clients).where(inArray(clients.id, ids))
  }
}
```

---

## 4. Authentication — RS256 JWT (NEVER HS256)

```typescript
// auth/jwt.ts
import jwt from 'jsonwebtoken'
import { readFileSync } from 'fs'
import { ApiError } from '../errors'

// ✅ RS256: private key signs, public key verifies
// Can distribute public key to microservices without exposing signing capability
const PRIVATE_KEY = readFileSync('./keys/private.pem')  // ⚠️ never commit to repo
const PUBLIC_KEY  = readFileSync('./keys/public.pem')

export interface JwtPayload {
  sub:   string        // userId
  email: string
  role:  'admin' | 'user' | 'service'
  iat?:  number
  exp?:  number
}

export function signToken(payload: Omit<JwtPayload, 'iat' | 'exp'>): string {
  return jwt.sign(payload, PRIVATE_KEY, {
    algorithm: 'RS256',
    expiresIn: '15m',   // ⚠️ ATENCIÓN: short-lived — always pair with refresh tokens
    issuer: 'automate.dev',
  })
}

export function verifyToken(token: string): JwtPayload {
  try {
    return jwt.verify(token, PUBLIC_KEY, {
      algorithms: ['RS256'],  // ✅ Whitelist — prevents algorithm confusion attacks
      issuer: 'automate.dev',
    }) as JwtPayload
  } catch (err) {
    if (err instanceof jwt.TokenExpiredError) throw new ApiError(401, 'Token expired')
    throw new ApiError(401, 'Invalid token')
  }
}

// Refresh token rotation — prevents race conditions
export async function rotateRefreshToken(
  oldToken: string,
  repo: RefreshTokenRepository
): Promise<{ accessToken: string; refreshToken: string }> {
  // ⚠️ ATENCIÓN: invalidate BEFORE issuing new — prevents replay attacks
  const record = await repo.findAndInvalidate(oldToken)
  if (!record || record.expiresAt < new Date()) {
    throw new ApiError(401, 'Refresh token invalid or expired')
  }
  const accessToken  = signToken({ sub: record.userId, email: record.email, role: record.role })
  const refreshToken = await repo.create(record.userId)
  return { accessToken, refreshToken }
}
```

---

## 5. RBAC Middleware

```typescript
// auth/rbac.ts
type Role = 'admin' | 'user' | 'service'
type Permission = 'clients:read' | 'clients:write' | 'clients:delete' | 'admin:all'

const ROLE_PERMISSIONS: Record<Role, Permission[]> = {
  admin:   ['clients:read', 'clients:write', 'clients:delete', 'admin:all'],
  user:    ['clients:read', 'clients:write'],
  service: ['clients:read'],
}

export function requirePermission(permission: Permission) {
  return (req: Request, res: Response, next: NextFunction) => {
    const user = req.user  // Set by auth middleware upstream
    if (!user) return res.status(401).json({ error: 'Unauthenticated' })

    const perms = ROLE_PERMISSIONS[user.role as Role] ?? []
    if (!perms.includes(permission)) {
      return res.status(403).json({ error: 'Insufficient permissions' })
    }
    next()
  }
}
```

---

## 6. Circuit Breaker + Retry (Resilience Patterns)

```typescript
// resilience/circuit-breaker.ts
import CircuitBreaker from 'opossum'  // npm install opossum

// ⚠️ ATENCIÓN: wrap EXTERNAL service calls only (3rd party APIs, external DBs)
export function createCircuitBreaker<T extends (...args: any[]) => Promise<any>>(
  fn: T,
  options?: Partial<CircuitBreaker.Options>
): CircuitBreaker {
  const breaker = new CircuitBreaker(fn, {
    timeout:                  5000,  // Mark failed if > 5s
    errorThresholdPercentage: 50,    // Open if 50%+ requests fail
    resetTimeout:             30000, // Half-open probe after 30s
    ...options,
  })

  breaker.on('open',     () => log.warn('Circuit OPEN — failing fast'))
  breaker.on('halfOpen', () => log.info('Circuit HALF-OPEN — probing'))
  breaker.on('close',    () => log.info('Circuit CLOSED — recovered'))

  return breaker
}

// Exponential backoff with jitter — prevents thundering herd
export async function withRetry<T>(
  fn: () => Promise<T>,
  { maxAttempts = 3, baseDelayMs = 1000, shouldRetry = (_e: unknown) => true } = {}
): Promise<T> {
  let lastError: Error

  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    try {
      return await fn()
    } catch (err) {
      lastError = err as Error
      if (!shouldRetry(err) || attempt === maxAttempts - 1) throw lastError
      const delay = baseDelayMs * Math.pow(2, attempt) + Math.random() * 200
      await new Promise(r => setTimeout(r, delay))
    }
  }
  throw lastError!
}
```

---

## 7. Background Jobs — BullMQ

```typescript
// jobs/queue.ts
import { Queue, Worker } from 'bullmq'  // npm install bullmq ioredis

const connection = { host: process.env.REDIS_HOST!, port: 6379 }

export const emailQueue = new Queue('email', { connection })

interface EmailJob {
  to: string; subject: string; templateId: string; vars: Record<string, unknown>
}

export const emailWorker = new Worker<EmailJob>(
  'email',
  async (job) => {
    // ⚠️ ATENCIÓN: worker crash = job re-queued automatically (BullMQ guarantees at-least-once)
    await sendEmail(job.data)
  },
  {
    connection,
    concurrency: 5,
    removeOnComplete: { count: 1000 },
    removeOnFail:     { count: 5000 },
  }
)

// API handler — async, 202 response
export async function queueEmail(data: EmailJob) {
  await emailQueue.add('send', data, {
    attempts: 3,
    backoff: { type: 'exponential', delay: 2000 },
  })
}
```

---

## 8. Pino Structured Logging

```typescript
// observability/logger.ts
import pino from 'pino'  // npm install pino pino-pretty

// ⚠️ ATENCIÓN: never console.log in production — not structured, not queryable
export const log = pino({
  level: process.env.LOG_LEVEL ?? 'info',
  transport: process.env.NODE_ENV !== 'production'
    ? { target: 'pino-pretty', options: { colorize: true } }
    : undefined,
  // ✅ Auto-redact sensitive fields from all log lines
  redact: ['req.headers.authorization', '*.apiKey', '*.password', '*.token'],
  base: { service: 'automate.dev-api', version: process.env.APP_VERSION },
})

export function requestLogger() {
  return (req: Request, res: Response, next: NextFunction) => {
    const requestId = crypto.randomUUID()
    req.requestId = requestId
    const start = Date.now()

    res.on('finish', () => {
      log.info({
        requestId,
        method:     req.method,
        path:       req.path,
        status:     res.statusCode,
        durationMs: Date.now() - start,
        userId:     req.user?.sub,
      }, 'HTTP request completed')
    })
    next()
  }
}
```

---

## 9. Centralized Error Handling

```typescript
// errors/index.ts
export class ApiError extends Error {
  constructor(
    public readonly statusCode: number,
    public readonly message: string,
    public readonly isOperational = true,
    public readonly context?: Record<string, unknown>
  ) {
    super(message)
    Object.setPrototypeOf(this, ApiError.prototype)
  }
}

// Register LAST in Express middleware chain
export function globalErrorHandler(
  err: unknown, req: Request, res: Response, _next: NextFunction
) {
  if (err instanceof ApiError) {
    if (!err.isOperational) {
      log.error({ err, requestId: req.requestId }, 'Non-operational error — requires alert')
    }
    return res.status(err.statusCode).json({ success: false, error: err.message })
  }

  if (err instanceof z.ZodError) {
    return res.status(400).json({
      success: false,
      error: 'Validation failed',
      issues: err.issues.map(i => ({ path: i.path, message: i.message }))
    })
  }

  log.error({ err, requestId: req.requestId }, 'Unhandled error')
  // ⚠️ ATENCIÓN: never leak stack trace in production response
  res.status(500).json({ success: false, error: 'Internal server error' })
}
```

---

## 10. Cache-Aside Pattern (LRU → Redis upgrade path)

```typescript
// cache/cache.service.ts
export async function cached<T>(
  cache: CacheDriver,
  key: string,
  ttlSeconds: number,
  fn: () => Promise<T>
): Promise<T> {
  const hit = await cache.get(key)
  if (hit) return JSON.parse(hit) as T

  const value = await fn()
  await cache.set(key, JSON.stringify(value), ttlSeconds)
  return value
}

// Usage
const client = await cached(
  redisCache,
  `client:${id}`,
  300,  // 5 min TTL
  () => clientRepo.findById(id)
)

// ⚠️ ATENCIÓN: always invalidate cache on mutations
await cache.del(`client:${id}`)
await clientRepo.update(id, data)
```

---

## 11. Rate Limiting (Redis-backed for multi-instance)

```typescript
import rateLimit from 'express-rate-limit'
import { RedisStore } from 'rate-limit-redis'

// ⚠️ ATENCIÓN: default in-memory store doesn't work across multiple Node processes
export const apiLimiter = rateLimit({
  windowMs:       60 * 1000,  // 1 minute
  max:            100,
  standardHeaders: true,
  legacyHeaders:  false,
  store:          new RedisStore({ client: redisClient, prefix: 'rl:' }),
  keyGenerator:   (req) => req.user?.sub ?? req.ip,  // Per-user when authenticated
  handler: (_req, res) =>
    res.status(429).json({ error: 'Rate limit exceeded', retryAfter: res.getHeader('Retry-After') }),
})
```

---

## Security Pre-Prod Checklist

```
✅ JWT: RS256 algorithm whitelisted, issuer verified
✅ JWT: short expiry (15m) + refresh token rotation with invalidation
✅ Input: Zod validation before any DB call or service logic
✅ DB: Drizzle parameterized queries (no string concat)
✅ DB: SQLite WAL mode, foreign_keys ON, busy_timeout set
✅ CORS: explicit allowed origins — no wildcards in prod
✅ Secrets: env vars only, never hardcoded or logged
✅ Logging: pino redact configured for auth headers, keys, passwords
✅ Rate limiting: Redis-backed store in multi-process deployments
✅ Errors: stack traces never exposed in API responses
✅ Background jobs: BullMQ with retry + failure retention
```

---

**Decision guide**: Repository + Service + Zod = baseline for every feature. Add CircuitBreaker when calling external APIs. Add BullMQ when any operation can be async. Add WAL + Redis when handling concurrent load.
