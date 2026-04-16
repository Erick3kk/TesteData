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
        print(f"[ERRO] {e}")
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
        return jsonify([{"id": r[0], "nome": r[1], "saldo": f"{r[2]:.2f}"} for r in cursor.fetchall()])
    finally: conn.close()

@app.route("/distribuir", methods=["POST"])
def distribuir_cashback():
    data = request.json
    id_alvo = data.get('id_evento') # Recebe o ID do campo de entrada
    
    conn = get_connection()
    if not conn: return jsonify({"status": "erro", "message": "Sem conexão"}), 500
    
    try:
        cursor = conn.cursor()
        # Bloco PL/SQL que filtra apenas pelo ID informado
        plsql_block = """
        DECLARE
            v_val NUMBER;
        BEGIN
            FOR reg IN (SELECT ID, USUARIO_ID, VALOR_PAGO, TIPO FROM INSCRICOES 
                        WHERE ID = :id AND STATUS = 'PRESENT') LOOP
                
                v_val := reg.VALOR_PAGO * 0.10; -- Exemplo de 10% fixo para simplificar
                
                UPDATE USUARIOS SET SALDO = SALDO + v_val WHERE ID = reg.USUARIO_ID;
                
                INSERT INTO LOG_AUDITORIA (INSCRICAO_ID, MOTIVO, DATA)
                VALUES (reg.ID, 'CASHBACK INDIVIDUAL APLICADO', SYSDATE);
            END LOOP;
            COMMIT;
        END;
        """
        cursor.execute(plsql_block, [id_alvo])
        return jsonify({"status": "sucesso", "message": f"Processado para o ID {id_alvo}!"})
    finally: conn.close()

@app.route("/reset", methods=["POST"])
def resetar_dados():
    conn = get_connection()
    if not conn: return jsonify({"status": "erro"}), 500
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE USUARIOS SET SALDO = 0") # Fix do reset
        cursor.execute("DELETE FROM LOG_AUDITORIA")
        conn.commit()
        return jsonify({"status": "sucesso", "message": "Sistema reiniciado!"})
    finally: conn.close()

if __name__ == "__main__":
    app.run(debug=True)