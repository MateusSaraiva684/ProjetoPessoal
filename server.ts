import express, { Request, Response, NextFunction } from 'express';
import cors from 'cors';
import cookieParser from 'cookie-parser';
import multer from 'multer';
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = 3000;
const HOST = '0.0.0.0';

// Upload configuration
const uploadDir = path.join(__dirname, 'uploads');
if (!fs.existsSync(uploadDir)) {
  fs.mkdirSync(uploadDir, { recursive: true });
}
const storage = multer.memoryStorage();
const upload = multer({ storage, limits: { fileSize: 10 * 1024 * 1024 } });

app.use(cors({ origin: true, credentials: true }));
app.use(cookieParser());
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true, limit: '10mb' }));

// In-Memory Database
interface Usuario {
  id: number;
  nome: string;
  email: string;
  senha: string;
  ativo: boolean;
  is_superuser: boolean;
  role: string;
  criado_em: string;
  total_alunos?: number;
}

interface Aluno {
  id: number;
  nome: string;
  numero_inscricao: string;
  telefone: string;
  turma: string;
  foto: string | null;
  empresa_id: number;
  user_id: number;
  external_id: string;
  biometria_status: string;
  biometria_error: string | null;
  biometria_atualizada_em: string | null;
  face_samples_count: number;
  criado_em: string;
  responsaveis?: any[];
}

interface Presenca {
  id: number;
  aluno_id: number;
  aluno_nome?: string;
  origem: string;
  tipo_evento: string;
  status: string;
  timestamp: string;
  camera_id: string;
  confianca: number;
}

interface Notificacao {
  id: number;
  aluno_id: number;
  aluno_nome: string;
  responsavel_nome: string;
  telefone: string;
  tipo: string;
  canal: string;
  mensagem: string;
  status: string;
  tentativas: number;
  criado_em: string;
}

interface AuditLog {
  id: number;
  actor_user_id: number;
  action: string;
  resource_type: string;
  resource_id: number | string;
  metadata: any;
  timestamp: string;
}

const usuarios: Usuario[] = [
  {
    id: 1,
    nome: 'Administrador do Sistema',
    email: 'admin@escola.com',
    senha: 'admin123',
    ativo: true,
    is_superuser: true,
    role: 'superadmin',
    criado_em: new Date(Date.now() - 30 * 86400000).toISOString(),
    total_alunos: 8,
  },
  {
    id: 2,
    nome: 'Diretoria - Colégio Modelo',
    email: 'diretoria@escola.com',
    senha: '123456',
    ativo: true,
    is_superuser: false,
    role: 'gestor',
    criado_em: new Date(Date.now() - 20 * 86400000).toISOString(),
    total_alunos: 8,
  }
];

const sampleAvatars = [
  'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150&auto=format&fit=crop&q=80',
  'https://images.unsplash.com/photo-1539571696357-5a69c17a67c6?w=150&auto=format&fit=crop&q=80',
  'https://images.unsplash.com/photo-1517841905240-472988babdf9?w=150&auto=format&fit=crop&q=80',
  'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=150&auto=format&fit=crop&q=80',
  'https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=150&auto=format&fit=crop&q=80',
  'https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=150&auto=format&fit=crop&q=80',
  'https://images.unsplash.com/photo-1524504388940-b1c1722653e1?w=150&auto=format&fit=crop&q=80',
  'https://images.unsplash.com/photo-1501196354995-cbb51c65aaea?w=150&auto=format&fit=crop&q=80',
];

let alunos: Aluno[] = [
  {
    id: 1,
    nome: 'Lucas Silva Santos',
    numero_inscricao: '2026001',
    telefone: '(11) 98765-4321',
    turma: '1º Ano A',
    foto: sampleAvatars[0],
    empresa_id: 2,
    user_id: 2,
    external_id: 'aluno_2026001',
    biometria_status: 'ready',
    biometria_error: null,
    biometria_atualizada_em: new Date(Date.now() - 2 * 86400000).toISOString(),
    face_samples_count: 3,
    criado_em: new Date(Date.now() - 15 * 86400000).toISOString(),
    responsaveis: [{ id: 1, nome: 'Carlos Silva', telefone: '(11) 98765-4321', email: 'carlos@email.com', parentesco: 'Pai' }]
  },
  {
    id: 2,
    nome: 'Beatriz de Oliveira Lima',
    numero_inscricao: '2026002',
    telefone: '(11) 97654-3210',
    turma: '1º Ano A',
    foto: sampleAvatars[1],
    empresa_id: 2,
    user_id: 2,
    external_id: 'aluno_2026002',
    biometria_status: 'ready',
    biometria_error: null,
    biometria_atualizada_em: new Date(Date.now() - 1 * 86400000).toISOString(),
    face_samples_count: 2,
    criado_em: new Date(Date.now() - 14 * 86400000).toISOString(),
    responsaveis: [{ id: 2, nome: 'Mariana Lima', telefone: '(11) 97654-3210', email: 'mariana@email.com', parentesco: 'Mãe' }]
  },
  {
    id: 3,
    nome: 'Gabriel Pereira Costa',
    numero_inscricao: '2026003',
    telefone: '(11) 96543-2109',
    turma: '1º Ano B',
    foto: sampleAvatars[2],
    empresa_id: 2,
    user_id: 2,
    external_id: 'aluno_2026003',
    biometria_status: 'ready',
    biometria_error: null,
    biometria_atualizada_em: new Date(Date.now() - 3 * 86400000).toISOString(),
    face_samples_count: 3,
    criado_em: new Date(Date.now() - 12 * 86400000).toISOString(),
    responsaveis: [{ id: 3, nome: 'Roberto Costa', telefone: '(11) 96543-2109', email: 'roberto@email.com', parentesco: 'Pai' }]
  },
  {
    id: 4,
    nome: 'Mariana Ferreira Rocha',
    numero_inscricao: '2026004',
    telefone: '(11) 95432-1098',
    turma: '2º Ano A',
    foto: sampleAvatars[3],
    empresa_id: 2,
    user_id: 2,
    external_id: 'aluno_2026004',
    biometria_status: 'ready',
    biometria_error: null,
    biometria_atualizada_em: new Date(Date.now() - 4 * 86400000).toISOString(),
    face_samples_count: 2,
    criado_em: new Date(Date.now() - 10 * 86400000).toISOString(),
    responsaveis: [{ id: 4, nome: 'Patricia Rocha', telefone: '(11) 95432-1098', email: 'patricia@email.com', parentesco: 'Mãe' }]
  },
  {
    id: 5,
    nome: 'Enzo Rodrigues Souza',
    numero_inscricao: '2026005',
    telefone: '(11) 94321-0987',
    turma: '2º Ano A',
    foto: sampleAvatars[4],
    empresa_id: 2,
    user_id: 2,
    external_id: 'aluno_2026005',
    biometria_status: 'ready',
    biometria_error: null,
    biometria_atualizada_em: new Date(Date.now() - 2 * 86400000).toISOString(),
    face_samples_count: 3,
    criado_em: new Date(Date.now() - 9 * 86400000).toISOString(),
    responsaveis: [{ id: 5, nome: 'Fabiana Souza', telefone: '(11) 94321-0987', email: 'fabiana@email.com', parentesco: 'Mãe' }]
  },
  {
    id: 6,
    nome: 'Sophia Martins Ramos',
    numero_inscricao: '2026006',
    telefone: '(11) 93210-9876',
    turma: '2º Ano B',
    foto: sampleAvatars[5],
    empresa_id: 2,
    user_id: 2,
    external_id: 'aluno_2026006',
    biometria_status: 'pending',
    biometria_error: null,
    biometria_atualizada_em: null,
    face_samples_count: 0,
    criado_em: new Date(Date.now() - 5 * 86400000).toISOString(),
    responsaveis: [{ id: 6, nome: 'Julio Ramos', telefone: '(11) 93210-9876', email: 'julio@email.com', parentesco: 'Pai' }]
  },
  {
    id: 7,
    nome: 'Guilherme Alves Ribeiro',
    numero_inscricao: '2026007',
    telefone: '(11) 92109-8765',
    turma: '3º Ano A',
    foto: sampleAvatars[6],
    empresa_id: 2,
    user_id: 2,
    external_id: 'aluno_2026007',
    biometria_status: 'ready',
    biometria_error: null,
    biometria_atualizada_em: new Date(Date.now() - 1 * 86400000).toISOString(),
    face_samples_count: 4,
    criado_em: new Date(Date.now() - 4 * 86400000).toISOString(),
    responsaveis: [{ id: 7, nome: 'Renata Ribeiro', telefone: '(11) 92109-8765', email: 'renata@email.com', parentesco: 'Mãe' }]
  },
  {
    id: 8,
    nome: 'Helena Carvalho Dias',
    numero_inscricao: '2026008',
    telefone: '(11) 91098-7654',
    turma: '3º Ano B',
    foto: null,
    empresa_id: 2,
    user_id: 2,
    external_id: 'aluno_2026008',
    biometria_status: 'no_photo',
    biometria_error: 'Foto ausente para extração biométrica',
    biometria_atualizada_em: null,
    face_samples_count: 0,
    criado_em: new Date(Date.now() - 2 * 86400000).toISOString(),
    responsaveis: [{ id: 8, nome: 'Eduardo Dias', telefone: '(11) 91098-7654', email: 'eduardo@email.com', parentesco: 'Pai' }]
  }
];

let presencas: Presenca[] = [
  {
    id: 101,
    aluno_id: 1,
    aluno_nome: 'Lucas Silva Santos',
    origem: 'facial',
    tipo_evento: 'entrada',
    status: 'confirmado',
    timestamp: new Date(Date.now() - 7 * 3600000).toISOString(),
    camera_id: 'CAM_PORTARIA_01',
    confianca: 0.98,
  },
  {
    id: 102,
    aluno_id: 2,
    aluno_nome: 'Beatriz de Oliveira Lima',
    origem: 'facial',
    tipo_evento: 'entrada',
    status: 'confirmado',
    timestamp: new Date(Date.now() - 6.8 * 3600000).toISOString(),
    camera_id: 'CAM_PORTARIA_01',
    confianca: 0.96,
  },
  {
    id: 103,
    aluno_id: 3,
    aluno_nome: 'Gabriel Pereira Costa',
    origem: 'facial',
    tipo_evento: 'entrada',
    status: 'confirmado',
    timestamp: new Date(Date.now() - 6.5 * 3600000).toISOString(),
    camera_id: 'CAM_PORTARIA_02',
    confianca: 0.94,
  },
  {
    id: 104,
    aluno_id: 4,
    aluno_nome: 'Mariana Ferreira Rocha',
    origem: 'manual',
    tipo_evento: 'entrada',
    status: 'confirmado',
    timestamp: new Date(Date.now() - 6.2 * 3600000).toISOString(),
    camera_id: 'MANUAL_OPERADOR',
    confianca: 1.0,
  },
  {
    id: 105,
    aluno_id: 5,
    aluno_nome: 'Enzo Rodrigues Souza',
    origem: 'facial',
    tipo_evento: 'entrada',
    status: 'confirmado',
    timestamp: new Date(Date.now() - 6.0 * 3600000).toISOString(),
    camera_id: 'CAM_PORTARIA_01',
    confianca: 0.97,
  },
  {
    id: 106,
    aluno_id: 7,
    aluno_nome: 'Guilherme Alves Ribeiro',
    origem: 'facial',
    tipo_evento: 'entrada',
    status: 'confirmado',
    timestamp: new Date(Date.now() - 5.9 * 3600000).toISOString(),
    camera_id: 'CAM_PORTARIA_01',
    confianca: 0.99,
  },
  {
    id: 107,
    aluno_id: 1,
    aluno_nome: 'Lucas Silva Santos',
    origem: 'facial',
    tipo_evento: 'saida',
    status: 'confirmado',
    timestamp: new Date(Date.now() - 1 * 3600000).toISOString(),
    camera_id: 'CAM_PORTARIA_SAIDA',
    confianca: 0.97,
  }
];

let notificacoes: Notificacao[] = [
  {
    id: 1,
    aluno_id: 1,
    aluno_nome: 'Lucas Silva Santos',
    responsavel_nome: 'Carlos Silva',
    telefone: '(11) 98765-4321',
    tipo: 'entrada',
    canal: 'WhatsApp',
    mensagem: 'Olá Carlos! Confirmamos a ENTRADA do aluno Lucas Silva Santos na escola às 07:15.',
    status: 'sent',
    tentativas: 1,
    criado_em: new Date(Date.now() - 7 * 3600000).toISOString(),
  },
  {
    id: 2,
    aluno_id: 2,
    aluno_nome: 'Beatriz de Oliveira Lima',
    responsavel_nome: 'Mariana Lima',
    telefone: '(11) 97654-3210',
    tipo: 'entrada',
    canal: 'WhatsApp',
    mensagem: 'Olá Mariana! Confirmamos a ENTRADA do aluno Beatriz de Oliveira Lima na escola às 07:22.',
    status: 'sent',
    tentativas: 1,
    criado_em: new Date(Date.now() - 6.8 * 3600000).toISOString(),
  },
  {
    id: 3,
    aluno_id: 3,
    aluno_nome: 'Gabriel Pereira Costa',
    responsavel_nome: 'Roberto Costa',
    telefone: '(11) 96543-2109',
    tipo: 'entrada',
    canal: 'WhatsApp',
    mensagem: 'Olá Roberto! Confirmamos a ENTRADA do aluno Gabriel Pereira Costa na escola às 07:35.',
    status: 'sent',
    tentativas: 1,
    criado_em: new Date(Date.now() - 6.5 * 3600000).toISOString(),
  },
  {
    id: 4,
    aluno_id: 4,
    aluno_nome: 'Mariana Ferreira Rocha',
    responsavel_nome: 'Patricia Rocha',
    telefone: '(11) 95432-1098',
    tipo: 'entrada',
    canal: 'WhatsApp',
    mensagem: 'Olá Patricia! Confirmamos a ENTRADA manual do aluno Mariana Ferreira Rocha na escola às 07:42.',
    status: 'sent',
    tentativas: 1,
    criado_em: new Date(Date.now() - 6.2 * 3600000).toISOString(),
  },
  {
    id: 5,
    aluno_id: 1,
    aluno_nome: 'Lucas Silva Santos',
    responsavel_nome: 'Carlos Silva',
    telefone: '(11) 98765-4321',
    tipo: 'saida',
    canal: 'WhatsApp',
    mensagem: 'Olá Carlos! Confirmamos a SAÍDA do aluno Lucas Silva Santos na portaria às 12:05.',
    status: 'sent',
    tentativas: 1,
    criado_em: new Date(Date.now() - 1 * 3600000).toISOString(),
  }
];

let auditLogs: AuditLog[] = [
  {
    id: 1,
    actor_user_id: 1,
    action: 'admin_login',
    resource_type: 'usuario',
    resource_id: 1,
    metadata: { ip: '127.0.0.1', user_agent: 'Browser' },
    timestamp: new Date(Date.now() - 10 * 3600000).toISOString(),
  },
  {
    id: 2,
    actor_user_id: 2,
    action: 'facial_sync_completed',
    resource_type: 'aluno',
    resource_id: 1,
    metadata: { samples: 3, duration_ms: 240 },
    timestamp: new Date(Date.now() - 8 * 3600000).toISOString(),
  }
];

let nextAlunoId = 9;
let nextPresencaId = 200;
let nextNotificacaoId = 10;
let nextUserId = 3;

// Helper to get authenticated user
function getAuthenticatedUser(req: Request): Usuario | null {
  const authHeader = req.headers.authorization;
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    // Check cookie
    const token = req.cookies?.refresh_token;
    if (token) {
      return usuarios[0];
    }
    return null;
  }
  const token = authHeader.substring(7);
  // Default to user with id encoded or matching email
  try {
    const parsed = JSON.parse(Buffer.from(token, 'base64').toString('utf-8'));
    return usuarios.find(u => u.id === parsed.id) || usuarios[0];
  } catch {
    return usuarios[0];
  }
}

function generateToken(usuario: Usuario): string {
  return Buffer.from(JSON.stringify({ id: usuario.id, email: usuario.email, time: Date.now() })).toString('base64');
}

// ─────────────────────────────────────────────────────────────────────────────
// 1. HEALTH CHECKS
// ─────────────────────────────────────────────────────────────────────────────
app.get('/api/health', (req, res) => {
  res.json({
    status: 'ok',
    version: '2.0.0',
    commit: 'v2.0.0-node',
    timestamp: new Date().toISOString(),
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// 2. AUTHENTICATION
// ─────────────────────────────────────────────────────────────────────────────
app.post('/api/auth/login', (req, res) => {
  const { email, senha } = req.body;
  if (!email || !senha) {
    return res.status(400).json({ erro: 'E-mail e senha são obrigatórios.' });
  }

  const user = usuarios.find(u => u.email.toLowerCase() === email.toLowerCase());
  if (!user || user.senha !== senha) {
    return res.status(401).json({ erro: 'Credenciais inválidas. Verifique seu e-mail e senha.' });
  }

  if (!user.ativo) {
    return res.status(403).json({ erro: 'Usuário desativado pelo administrador.' });
  }

  const token = generateToken(user);
  res.cookie('refresh_token', token, {
    httpOnly: true,
    maxAge: 7 * 86400 * 1000,
    path: '/api/auth',
  });

  auditLogs.unshift({
    id: auditLogs.length + 1,
    actor_user_id: user.id,
    action: 'login',
    resource_type: 'usuario',
    resource_id: user.id,
    metadata: { email: user.email },
    timestamp: new Date().toISOString(),
  });

  return res.json({
    access_token: token,
    expires_in: 86400,
    usuario: {
      id: user.id,
      nome: user.nome,
      email: user.email,
      ativo: user.ativo,
      is_superuser: user.is_superuser,
      role: user.role,
      criado_em: user.criado_em,
    },
  });
});

app.post('/api/auth/registrar', (req, res) => {
  const { nome, email, senha } = req.body;
  if (!nome || !email || !senha) {
    return res.status(400).json({ erro: 'Nome, e-mail e senha são obrigatórios.' });
  }

  if (usuarios.some(u => u.email.toLowerCase() === email.toLowerCase())) {
    return res.status(400).json({ erro: 'Já existe um usuário cadastrado com este e-mail.' });
  }

  const newUser: Usuario = {
    id: nextUserId++,
    nome: nome.trim(),
    email: email.trim().toLowerCase(),
    senha,
    ativo: true,
    is_superuser: false,
    role: 'gestor',
    criado_em: new Date().toISOString(),
    total_alunos: 0,
  };
  usuarios.push(newUser);

  return res.status(201).json({ mensagem: 'Conta criada com sucesso' });
});

app.post('/api/auth/refresh', (req, res) => {
  const user = getAuthenticatedUser(req) || usuarios[0];
  const token = generateToken(user);
  return res.json({
    access_token: token,
    expires_in: 86400,
    usuario: {
      id: user.id,
      nome: user.nome,
      email: user.email,
      ativo: user.ativo,
      is_superuser: user.is_superuser,
      role: user.role,
      criado_em: user.criado_em,
    },
  });
});

app.get('/api/auth/me', (req, res) => {
  const user = getAuthenticatedUser(req);
  if (!user) {
    return res.status(401).json({ erro: 'Não autenticado' });
  }
  return res.json({
    id: user.id,
    nome: user.nome,
    email: user.email,
    ativo: user.ativo,
    is_superuser: user.is_superuser,
    role: user.role,
    criado_em: user.criado_em,
  });
});

app.post('/api/auth/logout', (req, res) => {
  res.clearCookie('refresh_token', { path: '/api/auth' });
  return res.json({ mensagem: 'Logout realizado com sucesso' });
});

app.post('/api/auth/mfa/setup', (req, res) => {
  res.json({ otpauth_url: 'otpauth://totp/SistemaEscolar:admin@escola.com?secret=JBSWY3DPEHPK3PXP&issuer=SistemaEscolar' });
});

app.post('/api/auth/mfa/confirm', (req, res) => {
  res.json({ mensagem: 'MFA ativado com sucesso' });
});

// ─────────────────────────────────────────────────────────────────────────────
// 3. ALUNOS
// ─────────────────────────────────────────────────────────────────────────────
app.get('/api/alunos/turmas', (req, res) => {
  const turmasSet = new Set<string>();
  alunos.forEach(a => {
    if (a.turma) turmasSet.add(a.turma);
  });
  if (turmasSet.size === 0) {
    ['1º Ano A', '1º Ano B', '2º Ano A', '2º Ano B', '3º Ano A'].forEach(t => turmasSet.add(t));
  }
  return res.json(Array.from(turmasSet).sort());
});

app.get('/api/alunos/', (req, res) => {
  const { turma, busca, search, biometria_status, sem_foto, com_erro_biometria, page = '1', limit = '50' } = req.query;
  const searchTerm = (String(search || busca || '')).toLowerCase().trim();
  const pageNum = parseInt(String(page)) || 1;
  const limitNum = parseInt(String(limit)) || 50;

  let filtrados = [...alunos];

  if (turma) {
    filtrados = filtrados.filter(a => a.turma === turma);
  }
  if (searchTerm) {
    filtrados = filtrados.filter(a =>
      a.nome.toLowerCase().includes(searchTerm) ||
      a.numero_inscricao.toLowerCase().includes(searchTerm)
    );
  }
  if (biometria_status) {
    filtrados = filtrados.filter(a => a.biometria_status === biometria_status);
  }
  if (sem_foto === 'true') {
    filtrados = filtrados.filter(a => !a.foto);
  }
  if (com_erro_biometria === 'true') {
    filtrados = filtrados.filter(a => a.biometria_error || ['failed', 'needs_new_photo'].includes(a.biometria_status));
  }

  const total = filtrados.length;
  const totalPages = Math.ceil(total / limitNum) || 1;
  const startIndex = (pageNum - 1) * limitNum;
  const data = filtrados.slice(startIndex, startIndex + limitNum);

  return res.json({
    data,
    paginacao: {
      total,
      page: pageNum,
      limit: limitNum,
      total_pages: totalPages,
    }
  });
});

app.post('/api/alunos/', upload.single('foto') as any, (req: any, res: any) => {
  const currentUser = getAuthenticatedUser(req) || usuarios[0];
  const { nome, numero_inscricao, telefone, turma } = req.body;

  if (!nome || !numero_inscricao) {
    return res.status(400).json({ erro: 'Nome e número de inscrição são obrigatórios' });
  }

  // Handle uploaded photo or default avatar
  let fotoUrl = null;
  if (req.file) {
    fotoUrl = `data:${req.file.mimetype};base64,${req.file.buffer.toString('base64')}`;
  } else {
    fotoUrl = sampleAvatars[Math.floor(Math.random() * sampleAvatars.length)];
  }

  const novoAluno: Aluno = {
    id: nextAlunoId++,
    nome: nome.trim(),
    numero_inscricao: numero_inscricao.trim(),
    telefone: (telefone || '').trim(),
    turma: (turma || '').trim(),
    foto: fotoUrl,
    empresa_id: currentUser.id,
    user_id: currentUser.id,
    external_id: `aluno_${numero_inscricao.trim()}`,
    biometria_status: fotoUrl ? 'ready' : 'no_photo',
    biometria_error: fotoUrl ? null : 'Foto ausente para extração biométrica',
    biometria_atualizada_em: fotoUrl ? new Date().toISOString() : null,
    face_samples_count: fotoUrl ? 1 : 0,
    criado_em: new Date().toISOString(),
    responsaveis: []
  };

  alunos.unshift(novoAluno);

  auditLogs.unshift({
    id: auditLogs.length + 1,
    actor_user_id: currentUser.id,
    action: 'aluno_created',
    resource_type: 'aluno',
    resource_id: novoAluno.id,
    metadata: { nome: novoAluno.nome, turma: novoAluno.turma },
    timestamp: new Date().toISOString(),
  });

  return res.status(201).json(novoAluno);
});

app.get('/api/alunos/:id', (req: any, res: any) => {
  const id = parseInt(String(req.params.id));
  const aluno = alunos.find(a => a.id === id);
  if (!aluno) return res.status(404).json({ erro: 'Aluno não encontrado' });
  return res.json(aluno);
});

app.put('/api/alunos/:id', upload.single('foto') as any, (req: any, res: any) => {
  const id = parseInt(String(req.params.id));
  const index = alunos.findIndex(a => a.id === id);
  if (index === -1) return res.status(404).json({ erro: 'Aluno não encontrado' });

  const { nome, numero_inscricao, telefone, turma } = req.body;
  const aluno = alunos[index];

  if (nome) aluno.nome = nome.trim();
  if (numero_inscricao) {
    aluno.numero_inscricao = numero_inscricao.trim();
    aluno.external_id = `aluno_${aluno.numero_inscricao}`;
  }
  if (telefone !== undefined) aluno.telefone = telefone.trim();
  if (turma !== undefined) aluno.turma = turma.trim();

  if (req.file) {
    aluno.foto = `data:${req.file.mimetype};base64,${req.file.buffer.toString('base64')}`;
    aluno.biometria_status = 'ready';
    aluno.biometria_error = null;
    aluno.biometria_atualizada_em = new Date().toISOString();
    aluno.face_samples_count = Math.max(aluno.face_samples_count, 1) + 1;
  }

  return res.json(aluno);
});

app.delete('/api/alunos/:id', (req: any, res: any) => {
  const id = parseInt(String(req.params.id));
  alunos = alunos.filter(a => a.id !== id);
  presencas = presencas.filter(p => p.aluno_id !== id);
  return res.json({ mensagem: 'Aluno removido com sucesso' });
});

app.post('/api/alunos/:id/retry-biometria', (req: any, res: any) => {
  const id = parseInt(String(req.params.id));
  const aluno = alunos.find(a => a.id === id);
  if (!aluno) return res.status(404).json({ erro: 'Aluno não encontrado' });

  if (!aluno.foto) {
    aluno.foto = sampleAvatars[Math.floor(Math.random() * sampleAvatars.length)];
  }

  aluno.biometria_status = 'ready';
  aluno.biometria_error = null;
  aluno.biometria_atualizada_em = new Date().toISOString();
  aluno.face_samples_count = Math.max(aluno.face_samples_count, 1);

  return res.json(aluno);
});

app.delete('/api/alunos/:id/biometria', (req: any, res: any) => {
  const id = parseInt(String(req.params.id));
  const aluno = alunos.find(a => a.id === id);
  if (!aluno) return res.status(404).json({ erro: 'Aluno não encontrado' });

  aluno.biometria_status = 'no_photo';
  aluno.face_samples_count = 0;
  aluno.biometria_error = 'Biometria removida manualmente';
  return res.json({ mensagem: 'Biometria removida com sucesso' });
});

app.get('/api/alunos/:id/fotos', (req: any, res: any) => {
  const id = parseInt(String(req.params.id));
  const aluno = alunos.find(a => a.id === id);
  if (!aluno) return res.status(404).json({ erro: 'Aluno não encontrado' });

  const fotos = aluno.foto ? [
    { id: 1, aluno_id: id, foto_url: aluno.foto, criado_em: aluno.biometria_atualizada_em || aluno.criado_em }
  ] : [];
  return res.json(fotos);
});

app.post('/api/alunos/:id/fotos', upload.single('foto') as any, (req: any, res: any) => {
  const id = parseInt(String(req.params.id));
  const aluno = alunos.find(a => a.id === id);
  if (!aluno) return res.status(404).json({ erro: 'Aluno não encontrado' });

  let fotoUrl = aluno.foto;
  if (req.file) {
    fotoUrl = `data:${req.file.mimetype};base64,${req.file.buffer.toString('base64')}`;
    aluno.foto = fotoUrl;
    aluno.biometria_status = 'ready';
    aluno.biometria_error = null;
    aluno.biometria_atualizada_em = new Date().toISOString();
    aluno.face_samples_count = (aluno.face_samples_count || 0) + 1;
  }

  return res.status(201).json({
    id: Date.now(),
    aluno_id: id,
    foto_url: fotoUrl,
    criado_em: new Date().toISOString()
  });
});

app.post('/api/alunos/:id/responsaveis', (req: any, res: any) => {
  const id = parseInt(String(req.params.id));
  const aluno = alunos.find(a => a.id === id);
  if (!aluno) return res.status(404).json({ erro: 'Aluno não encontrado' });

  const { nome, telefone, email, parentesco } = req.body;
  const novoResp = {
    id: Date.now(),
    nome: nome || 'Responsável',
    telefone: telefone || '',
    email: email || '',
    parentesco: parentesco || 'Responsável'
  };
  if (!aluno.responsaveis) aluno.responsaveis = [];
  aluno.responsaveis.push(novoResp);
  return res.status(201).json(novoResp);
});

// ─────────────────────────────────────────────────────────────────────────────
// 4. PRESENÇAS
// ─────────────────────────────────────────────────────────────────────────────
app.get('/api/presencas', (req, res) => {
  const { aluno_id, inicio, fim, camera_id } = req.query;
  let filtradas = [...presencas];

  if (aluno_id) {
    filtradas = filtradas.filter(p => String(p.aluno_id) === String(aluno_id));
  }
  if (camera_id) {
    filtradas = filtradas.filter(p => p.camera_id === camera_id);
  }
  if (inicio) {
    const inicioDate = new Date(String(inicio)).getTime();
    filtradas = filtradas.filter(p => new Date(p.timestamp).getTime() >= inicioDate);
  }
  if (fim) {
    const fimDate = new Date(String(fim)).getTime();
    filtradas = filtradas.filter(p => new Date(p.timestamp).getTime() <= fimDate);
  }

  // Attach student objects
  const resultado = filtradas.map(p => {
    const aluno = alunos.find(a => a.id === p.aluno_id);
    return {
      ...p,
      aluno_nome: aluno?.nome || p.aluno_nome,
      turma: aluno?.turma || '',
      numero_inscricao: aluno?.numero_inscricao || '',
      aluno: aluno || null,
    };
  });

  return res.json(resultado);
});

app.get('/api/presencas/aluno/:id', (req: any, res: any) => {
  const alunoId = parseInt(String(req.params.id));
  const lista = presencas.filter(p => p.aluno_id === alunoId);
  return res.json(lista);
});

function registrarEventoPresenca(alunoId: number, tipoEvento: string, origem: string = 'manual', cameraId: string = 'MANUAL_OPERADOR', confianca: number = 1.0) {
  const aluno = alunos.find(a => a.id === alunoId);
  if (!aluno) throw new Error('Aluno não encontrado');

  const novaPresenca: Presenca = {
    id: nextPresencaId++,
    aluno_id: aluno.id,
    aluno_nome: aluno.nome,
    origem,
    tipo_evento: tipoEvento,
    status: 'confirmado',
    timestamp: new Date().toISOString(),
    camera_id: cameraId,
    confianca,
  };

  presencas.unshift(novaPresenca);

  // Trigger Notification to parent
  const novaNotif: Notificacao = {
    id: nextNotificacaoId++,
    aluno_id: aluno.id,
    aluno_nome: aluno.nome,
    responsavel_nome: aluno.responsaveis?.[0]?.nome || 'Responsável',
    telefone: aluno.responsaveis?.[0]?.telefone || aluno.telefone || '(11) 98765-4321',
    tipo: tipoEvento,
    canal: 'WhatsApp',
    mensagem: `Olá! Confirmamos a ${tipoEvento.toUpperCase()} do(a) aluno(a) ${aluno.nome} na escola (${origem === 'facial' ? 'Reconhecimento Facial' : 'Portaria'}).`,
    status: 'sent',
    tentativas: 1,
    criado_em: new Date().toISOString(),
  };
  notificacoes.unshift(novaNotif);

  return novaPresenca;
}

app.post('/api/presencas/manual', (req, res) => {
  const { aluno_id } = req.body;
  if (!aluno_id) return res.status(400).json({ erro: 'aluno_id é obrigatório' });
  try {
    const presenca = registrarEventoPresenca(Number(aluno_id), 'entrada', 'manual', 'OPERADOR_SISTEMA', 1.0);
    return res.status(201).json(presenca);
  } catch (err: any) {
    return res.status(404).json({ erro: err.message });
  }
});

app.post('/api/presencas/entrada', (req, res) => {
  const { aluno_id } = req.body;
  if (!aluno_id) return res.status(400).json({ erro: 'aluno_id é obrigatório' });
  try {
    const presenca = registrarEventoPresenca(Number(aluno_id), 'entrada', 'manual', 'PORTARIA_ENTRADA', 1.0);
    return res.status(201).json(presenca);
  } catch (err: any) {
    return res.status(404).json({ erro: err.message });
  }
});

app.post('/api/presencas/saida', (req, res) => {
  const { aluno_id } = req.body;
  if (!aluno_id) return res.status(400).json({ erro: 'aluno_id é obrigatório' });
  try {
    const presenca = registrarEventoPresenca(Number(aluno_id), 'saida', 'manual', 'PORTARIA_SAIDA', 1.0);
    return res.status(201).json(presenca);
  } catch (err: any) {
    return res.status(404).json({ erro: err.message });
  }
});

app.get('/api/presencas/exportar/csv', (req, res) => {
  let csv = 'ID,Aluno,Inscrição,Turma,Tipo,Origem,Status,Camera,Data e Hora,Confiança\n';
  presencas.forEach(p => {
    const aluno = alunos.find(a => a.id === p.aluno_id);
    csv += `"${p.id}","${p.aluno_nome || aluno?.nome || ''}","${aluno?.numero_inscricao || ''}","${aluno?.turma || ''}","${p.tipo_evento}","${p.origem}","${p.status}","${p.camera_id}","${p.timestamp}","${(p.confianca * 100).toFixed(1)}%"\n`;
  });
  res.setHeader('Content-Type', 'text/csv');
  res.setHeader('Content-Disposition', 'attachment; filename=relatorio_presencas.csv');
  return res.send(csv);
});

// ─────────────────────────────────────────────────────────────────────────────
// 5. RECONHECIMENTO FACIAL
// ─────────────────────────────────────────────────────────────────────────────
app.post('/api/reconhecimento/identificar', upload.single('file') as any, (req: any, res: any) => {
  // Pick an existing student with biometrics ready as top match
  const alunosComBiometria = alunos.filter(a => a.biometria_status === 'ready');
  const matchedAluno = alunosComBiometria.length > 0
    ? alunosComBiometria[Math.floor(Math.random() * alunosComBiometria.length)]
    : alunos[0];

  if (!matchedAluno) {
    return res.status(400).json({ erro: 'Nenhum aluno cadastrado para reconhecimento' });
  }

  // Register presence
  const presenca = registrarEventoPresenca(matchedAluno.id, 'entrada', 'facial', 'CAM_PORTARIA_01', 0.98);

  return res.json({
    match: true,
    aluno_id: matchedAluno.id,
    aluno: {
      id: matchedAluno.id,
      nome: matchedAluno.nome,
      turma: matchedAluno.turma,
      numero_inscricao: matchedAluno.numero_inscricao,
      foto: matchedAluno.foto,
      biometria_status: matchedAluno.biometria_status,
    },
    confidence: 0.98,
    timestamp: presenca.timestamp,
    camera_id: 'CAM_PORTARIA_01',
    message: `Aluno ${matchedAluno.nome} reconhecido com 98% de confiança!`
  });
});

app.post('/api/reconhecimento/facial', upload.single('imagem') as any, (req: any, res: any) => {
  const alunosComBiometria = alunos.filter(a => a.biometria_status === 'ready');
  const matchedAluno = alunosComBiometria[0] || alunos[0];

  if (matchedAluno) {
    registrarEventoPresenca(matchedAluno.id, 'entrada', 'facial', 'CAM_PORTARIA_01', 0.97);
  }

  return res.json({
    sucesso: true,
    aluno: matchedAluno,
    confianca: 0.97,
    mensagem: 'Reconhecimento facial processado com sucesso.'
  });
});

app.post('/api/recognition/presences', (req, res) => {
  res.json({ status: 'received' });
});

// ─────────────────────────────────────────────────────────────────────────────
// 6. NOTIFICAÇÕES
// ─────────────────────────────────────────────────────────────────────────────
app.get('/api/notificacoes', (req, res) => {
  const { status, page = '1', limit = '25' } = req.query;
  const pageNum = parseInt(String(page)) || 1;
  const limitNum = parseInt(String(limit)) || 25;

  let filtradas = [...notificacoes];
  if (status) {
    filtradas = filtradas.filter(n => n.status === status);
  }

  const startIndex = (pageNum - 1) * limitNum;
  const data = filtradas.slice(startIndex, startIndex + limitNum);
  return res.json(data);
});

app.post('/api/notificacoes/:id/retry', (req: any, res: any) => {
  const id = parseInt(String(req.params.id));
  const notif = notificacoes.find(n => n.id === id);
  if (!notif) return res.status(404).json({ erro: 'Notificação não encontrada' });

  notif.status = 'sent';
  notif.tentativas += 1;
  return res.json({ mensagem: 'Reenvio solicitado', ok: true });
});

// ─────────────────────────────────────────────────────────────────────────────
// 7. ADMIN PANEL
// ─────────────────────────────────────────────────────────────────────────────
app.get('/api/admin/stats', (req, res) => {
  const presencasHoje = presencas.length;
  const presencasFacial = presencas.filter(p => p.origem === 'facial').length;
  const taxa = presencasHoje > 0 ? `${((presencasFacial / presencasHoje) * 100).toFixed(1)}%` : '100%';

  return res.json({
    total_usuarios: usuarios.length,
    total_alunos: alunos.length,
    total_presencas_hoje: presencasHoje,
    total_notificacoes_hoje: notificacoes.length,
    taxa_reconhecimento: taxa,
  });
});

app.get('/api/admin/usuarios', (req, res) => {
  const lista = usuarios.map(u => ({
    id: u.id,
    nome: u.nome,
    email: u.email,
    ativo: u.ativo,
    is_superuser: u.is_superuser,
    role: u.role,
    criado_em: u.criado_em,
    total_alunos: alunos.filter(a => a.user_id === u.id || a.empresa_id === u.id).length,
  }));
  return res.json(lista);
});

app.post('/api/admin/usuarios', (req, res) => {
  const { nome, email, senha, is_superuser } = req.body;
  if (!nome || !email || !senha) {
    return res.status(400).json({ erro: 'Nome, e-mail e senha são obrigatórios' });
  }

  const novo: Usuario = {
    id: nextUserId++,
    nome: nome.trim(),
    email: email.trim().toLowerCase(),
    senha,
    ativo: true,
    is_superuser: Boolean(is_superuser),
    role: is_superuser ? 'superadmin' : 'gestor',
    criado_em: new Date().toISOString(),
    total_alunos: 0,
  };
  usuarios.push(novo);
  return res.status(201).json(novo);
});

app.patch('/api/admin/usuarios/:id', (req: any, res: any) => {
  const id = parseInt(String(req.params.id));
  const user = usuarios.find(u => u.id === id);
  if (!user) return res.status(404).json({ erro: 'Usuário não encontrado' });

  if (req.body.nome) user.nome = req.body.nome.trim();
  if (req.body.email) user.email = req.body.email.trim().toLowerCase();
  return res.json(user);
});

app.patch('/api/admin/usuarios/:id/senha', (req: any, res: any) => {
  const id = parseInt(String(req.params.id));
  const user = usuarios.find(u => u.id === id);
  if (!user) return res.status(404).json({ erro: 'Usuário não encontrado' });

  const { nova_senha } = req.body;
  if (!nova_senha || nova_senha.length < 6) {
    return res.status(400).json({ erro: 'A senha deve ter no mínimo 6 caracteres' });
  }
  user.senha = nova_senha;
  return res.json({ mensagem: 'Senha atualizada com sucesso' });
});

app.patch('/api/admin/usuarios/:id/ativo', (req: any, res: any) => {
  const id = parseInt(String(req.params.id));
  const user = usuarios.find(u => u.id === id);
  if (!user) return res.status(404).json({ erro: 'Usuário não encontrado' });

  user.ativo = !user.ativo;
  return res.json({ id: user.id, ativo: user.ativo });
});

app.delete('/api/admin/usuarios/:id', (req: any, res: any) => {
  const id = parseInt(String(req.params.id));
  const user = usuarios.find(u => u.id === id);
  if (!user) return res.status(404).json({ erro: 'Usuário não encontrado' });
  if (user.is_superuser && usuarios.filter(u => u.is_superuser).length <= 1) {
    return res.status(400).json({ erro: 'Não é possível remover o único superusuário' });
  }

  const idx = usuarios.findIndex(u => u.id === id);
  usuarios.splice(idx, 1);
  alunos = alunos.filter(a => a.user_id !== id && a.empresa_id !== id);
  return res.json({ mensagem: 'Usuário e dados vinculados removidos com sucesso' });
});

app.get('/api/admin/escolas', (req, res) => {
  const escolas = usuarios
    .filter(u => !u.is_superuser)
    .map(u => ({
      id: u.id,
      nome: u.nome,
      email: u.email,
      total_alunos: alunos.filter(a => a.empresa_id === u.id || a.user_id === u.id).length,
      criado_em: u.criado_em,
    }));
  return res.json(escolas);
});

app.get('/api/admin/escolas/:id/alunos', (req: any, res: any) => {
  const id = parseInt(String(req.params.id));
  const lista = alunos.filter(a => a.empresa_id === id || a.user_id === id);
  return res.json(lista);
});

app.get('/api/admin/alunos', (req, res) => {
  return res.json({
    data: alunos,
    paginacao: {
      total: alunos.length,
      page: 1,
      limit: 100,
      total_pages: 1,
    }
  });
});

app.delete('/api/admin/alunos/:id', (req: any, res: any) => {
  const id = parseInt(String(req.params.id));
  alunos = alunos.filter(a => a.id !== id);
  presencas = presencas.filter(p => p.aluno_id !== id);
  return res.json({ mensagem: 'Aluno removido com sucesso' });
});

app.get('/api/admin/system-health', (req, res) => {
  return res.json({
    status: 'healthy',
    database: 'online',
    recognition_service: 'online',
    redis: 'in_memory_ready',
    uptime_seconds: Math.floor(process.uptime()),
    timestamp: new Date().toISOString(),
  });
});

app.get('/api/admin/audit-logs', (req, res) => {
  return res.json(auditLogs);
});

// ─────────────────────────────────────────────────────────────────────────────
// 8. VITE MIDDLEWARE / STATIC ASSETS
// ─────────────────────────────────────────────────────────────────────────────
async function startServer() {
  if (process.env.NODE_ENV !== 'production') {
    const { createServer: createViteServer } = await import('vite');
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: 'spa',
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(__dirname, 'dist');
    app.use(express.static(distPath));
    app.get('*', (req, res) => {
      res.sendFile(path.join(distPath, 'index.html'));
    });
  }

  app.listen(PORT, HOST, () => {
    console.log(`[Sistema Escolar] Dev server running on http://${HOST}:${PORT}`);
  });
}

startServer().catch(err => {
  console.error('[Sistema Escolar] Failed to start server:', err);
  process.exit(1);
});
