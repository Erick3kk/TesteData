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
        print(f"Erro Conexão: {e}")
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
    data = request.get_json()
    id_alvo = data.get('id_evento')
    
    conn = get_connection()
    if not conn: return jsonify({"status": "erro", "message": "Sem conexão com o banco"}), 500
    
    try:
        cursor = conn.cursor()
        # Variável para contar quantos registros foram afetados
        v_count = cursor.var(oracledb.NUMBER)
        
        plsql_block = """
        DECLARE
            v_taxa NUMBER;
            v_cont NUMBER := 0;
        BEGIN
            FOR reg IN (SELECT ID, USUARIO_ID, VALOR_PAGO, TIPO 
                        FROM INSCRICOES WHERE ID = :id_input AND STATUS = 'PRESENT') LOOP
                
                -- Lógica: >3 presenças = 25%, VIP = 20%, Resto = 10%
                IF (SELECT COUNT(*) FROM INSCRICOES WHERE USUARIO_ID = reg.USUARIO_ID AND STATUS = 'PRESENT') > 3 THEN
                    v_taxa := 0.25;
                ELSIF reg.TIPO = 'VIP' THEN
                    v_taxa := 0.20;
                ELSE
                    v_taxa := 0.10;
                END IF;

                UPDATE USUARIOS SET SALDO = SALDO + (reg.VALOR_PAGO * v_taxa) WHERE ID = reg.USUARIO_ID;
                
                INSERT INTO LOG_AUDITORIA (INSCRICAO_ID, MOTIVO, DATA)
                VALUES (reg.ID, 'CASHBACK INDIVIDUAL APLICADO', SYSDATE);
                v_cont := v_cont + 1;
            END LOOP;
            :v_saida := v_cont;
            COMMIT;
        END;
        """
        cursor.execute(plsql_block, id_input=id_alvo, v_saida=v_count)
        
        if v_count.getvalue() == 0:
            return jsonify({"status": "erro", "message": f"Nenhum registro encontrado para o ID {id_alvo}"})
            
        return jsonify({"status": "sucesso", "message": f"Cashback aplicado com sucesso ao ID {id_alvo}!"})
    except Exception as e:
        return jsonify({"status": "erro", "message": str(e)}), 500
    finally: conn.close()

@app.route("/reset", methods=["POST"])
def resetar_dados():
    conn = get_connection()
    if not conn: return jsonify({"status": "erro"}), 500
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE USUARIOS SET SALDO = 100") # Reseta para 100
        cursor.execute("DELETE FROM LOG_AUDITORIA")
        conn.commit()
        return jsonify({"status": "sucesso", "message": "Sistema resetado para R$ 100,00!"})
    finally: conn.close()

if __name__ == "__main__":
    app.run(debug=True)