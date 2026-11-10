PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY,
    nome TEXT NOT NULL,
    email TEXT NOT NULL COLLATE NOCASE UNIQUE
);

CREATE TABLE IF NOT EXISTS construtoras (
    id INTEGER PRIMARY KEY,
    nome TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS obras (
    id INTEGER PRIMARY KEY,
    construtora_id INTEGER NOT NULL REFERENCES construtoras(id),
    nome TEXT NOT NULL,
    local TEXT,
    data_inicio TEXT,
    previsao_entrega TEXT,
    status TEXT NOT NULL DEFAULT 'planejada'
        CHECK (status IN ('planejada', 'em_andamento', 'concluida'))
);

CREATE TABLE IF NOT EXISTS participantes_obra (
    obra_id INTEGER NOT NULL REFERENCES obras(id),
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
    perfil TEXT NOT NULL CHECK (perfil IN ('construtora', 'mestre_de_obras', 'cliente')),
    PRIMARY KEY (obra_id, usuario_id, perfil)
);

CREATE TABLE IF NOT EXISTS etapas (
    id INTEGER PRIMARY KEY,
    obra_id INTEGER NOT NULL REFERENCES obras(id),
    nome TEXT NOT NULL,
    ordem INTEGER NOT NULL CHECK (ordem >= 1),
    prazo TEXT,
    progresso INTEGER NOT NULL DEFAULT 0 CHECK (progresso BETWEEN 0 AND 100),
    UNIQUE (obra_id, ordem)
);

CREATE TABLE IF NOT EXISTS registros_diario (
    id INTEGER PRIMARY KEY,
    obra_id INTEGER NOT NULL,
    autor_id INTEGER NOT NULL,
    perfil_autor TEXT NOT NULL
        CHECK (perfil_autor IN ('construtora', 'mestre_de_obras')),
    data_registro TEXT NOT NULL,
    atividades TEXT NOT NULL,
    equipe TEXT,
    condicoes TEXT,
    proxima_atividade TEXT,
    status TEXT NOT NULL DEFAULT 'rascunho'
        CHECK (status IN ('rascunho', 'finalizado')),
    compartilhado_com_cliente INTEGER NOT NULL DEFAULT 0
        CHECK (compartilhado_com_cliente IN (0, 1)),
    CHECK (compartilhado_com_cliente = 0 OR status = 'finalizado'),
    FOREIGN KEY (obra_id, autor_id, perfil_autor)
        REFERENCES participantes_obra (obra_id, usuario_id, perfil)
);

CREATE TABLE IF NOT EXISTS fotos_diario (
    id INTEGER PRIMARY KEY,
    registro_id INTEGER NOT NULL REFERENCES registros_diario(id),
    caminho TEXT NOT NULL,
    legenda TEXT
);
