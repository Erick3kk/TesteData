import oracledb
import os
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

def get_connection():
    try:
        return oracledb.connect(
            user=os.environ.get("DB_USER"),
            password=os.environ.get("DB_PASSWORD"),
            dsn=os.environ.get("DB_DSN"),
        )
    except Exception as e:
        print(f"Erro Conexao: {e}")
        return None

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/usuarios", methods=["GET"])
def listar_usuarios():
    conn = get_connection()
    if not conn: return jsonify([]), 500
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT ID, NOME, SALDO FROM USUARIOS ORDER BY ID")
        res = [{"id": r[0], "nome": r[1], "saldo": f"{r[2]:.2f}"} for r in cursor.fetchall()]
        return jsonify(res)
    finally: conn.close()

@app.route("/distribuir", methods=["POST"])
def distribuir_cashback():
    data = request.get_json()
    try:
        # Forçamos o ID a ser um número inteiro aqui no Python
        id_alvo = int(data.get('id_evento'))
    except:
        return jsonify({"status": "erro", "message": "ID Inválido"}), 400

    conn = get_connection()
    if not conn: return jsonify({"status": "erro", "message": "Sem conexão"}), 500
    
    try:
        cursor = conn.cursor()
        
        # SQL puro com subquery para evitar erros de bloco PL/SQL complexo
        # Esta query faz: 
        # 1. Busca a inscrição pelo ID 
        # 2. Calcula 25% se tiver >3 presenças, senão 20% se VIP, senão 10%
        # 3. Atualiza o saldo do usuário vinculado
        
        sql_update = """
        UPDATE USUARIOS u
        SET u.SALDO = u.SALDO + (
            SELECT i.VALOR_PAGO * (
                CASE 
                    WHEN (SELECT COUNT(*) FROM INSCRICOES WHERE USUARIO_ID = i.USUARIO_ID AND STATUS = 'PRESENT') > 3 THEN 0.25
                    WHEN i.TIPO = 'VIP' THEN 0.20
                    ELSE 0.10
                END
            )
            FROM INSCRICOES i
            WHERE i.ID = :1 AND i.STATUS = 'PRESENT' AND i.USUARIO_ID = u.ID
        )
        WHERE EXISTS (
            SELECT 1 FROM INSCRICOES i 
            WHERE i.ID = :1 AND i.STATUS = 'PRESENT' AND i.USUARIO_ID = u.ID
        )
        """
        
        cursor.execute(sql_update, [id_alvo])
        
        if cursor.rowcount == 0:
            return jsonify({"status": "erro", "message": f"ID {id_alvo} não encontrado ou não está presente."})

        # Registrar no Log
        cursor.execute("""
            INSERT INTO LOG_AUDITORIA (INSCRICAO_ID, MOTIVO, DATA)
            VALUES (:1, 'CASHBACK INDIVIDUAL PROCESSADO', SYSDATE)
        """, [id_alvo])
        
        conn.commit()
        return jsonify({"status": "sucesso", "message": f"Cashback aplicado ao ID {id_alvo}!"})
    except Exception as e:
        return jsonify({"status": "erro", "message": str(e)}), 500
    finally: conn.close()

@app.route("/reset", methods=["POST"])
def resetar_dados():
    conn = get_connection()
    if not conn: return jsonify({"status": "erro"}), 500
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE USUARIOS SET SALDO = 100")
        cursor.execute("DELETE FROM LOG_AUDITORIA")
        conn.commit()
        return jsonify({"status": "sucesso", "message": "Saldos resetados para R$ 100,00!"})
    finally: conn.close()

if __name__ == "__main__":
    app.run(debug=True)