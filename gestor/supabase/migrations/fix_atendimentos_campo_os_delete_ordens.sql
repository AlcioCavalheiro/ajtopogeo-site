-- ╔═══════════════════════════════════════════════════════════════════════╗
-- ║ FIX — excluir OS falhava com FK violation em atendimentos_campo_os     ║
-- ║ os_id era NOT NULL; ao excluir uma OS com diário de bordo (turno de    ║
-- ║ campo) vinculado, o delete travava. Agora fica nullable (como as       ║
-- ║ demais tabelas ligadas a ordens) e o registro de campo é preservado,   ║
-- ║ só perde o vínculo com a OS (os_numero continua guardado no registro). ║
-- ╚═══════════════════════════════════════════════════════════════════════╝

alter table atendimentos_campo_os alter column os_id drop not null;
