import logging
from typing import Any, Dict, List, Optional
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
import json
import secrets
import string

# Configuração profissional de logs (data, nível e mensagem)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("AWSManager")


class AWSManager:
    def __init__(self, endpoint_url: str = "http://localhost:4566", region_name: str = "us-east-1"):
        self.endpoint_url = endpoint_url
        self.region_name = region_name
        
        self.aws_access_key_id = "test"
        self.aws_secret_access_key = "test"

        # Força path-style para evitar erros de DNS local no Windows com LocalStack
        config_s3 = Config(
            s3={'addressing_style': 'path'},
            retries={'max_attempts': 3, 'mode': 'standard'}
        )

        self.s3_client = boto3.client(
            's3',
            endpoint_url=self.endpoint_url,
            region_name=self.region_name,
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            config=config_s3
        )

        self.dynamodb_client = boto3.client(
            'dynamodb',
            endpoint_url=self.endpoint_url,
            region_name=self.region_name,
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key
        )

        self.secrets_client = boto3.client(
            'secretsmanager',
            endpoint_url=self.endpoint_url,
            region_name=self.region_name,
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key
        )

        self.sqs_client = boto3.client(
            'sqs',
            endpoint_url=self.endpoint_url,
            region_name=self.region_name,
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key
        )

        self.sns_client = boto3.client(
            'sns',
            endpoint_url=self.endpoint_url,
            region_name=self.region_name,
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key
        )

    # =========================================================================
    # OPERAÇÕES BÁSICAS DE BUCKET E ARQUIVOS FÍSICOS
    # =========================================================================

    def criar_bucket(self, bucket_name: str) -> bool:
        """Cria um novo bucket no S3."""
        try:
            self.s3_client.create_bucket(Bucket=bucket_name)
            logger.info(f"Bucket '{bucket_name}' criado com sucesso.")
            return True
        except ClientError as e:
            logger.error(f"Erro AWS ao criar bucket '{bucket_name}': {e.response['Error']['Message']}")
            return False
        except Exception as e:
            logger.error(f"Erro inesperado ao criar bucket '{bucket_name}': {e}")
            return False

    def listar_buckets(self) -> List[str]:
        """Retorna e registra todos os buckets disponíveis."""
        try:
            response = self.s3_client.list_buckets()
            buckets = [b['Name'] for b in response.get('Buckets', [])]
            logger.info(f"Buckets encontrados ({len(buckets)}): {buckets}")
            return buckets
        except Exception as e:
            logger.error(f"Erro ao listar buckets: {e}")
            return []

    def enviar_arquivo(
        self,
        file_name: str,
        bucket_name: str,
        object_name: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None
    ) -> bool:
        """Faz upload de um arquivo físico do disco para o S3, com suporte a metadados."""
        if object_name is None:
            object_name = file_name

        extra_args = {}
        if metadata:
            extra_args['Metadata'] = metadata

        try:
            self.s3_client.upload_file(file_name, bucket_name, object_name, ExtraArgs=extra_args)
            logger.info(f"Arquivo '{file_name}' enviado para '{bucket_name}/{object_name}'.")
            return True
        except Exception as e:
            logger.error(f"Erro ao enviar arquivo '{file_name}': {e}")
            return False

    def baixar_arquivo(self, bucket_name: str, object_name: str, file_name: str) -> bool:
        """Baixa um objeto do S3 para um arquivo local no disco."""
        try:
            self.s3_client.download_file(bucket_name, object_name, file_name)
            logger.info(f"Objeto '{object_name}' baixado para '{file_name}'.")
            return True
        except Exception as e:
            logger.error(f"Erro ao baixar '{object_name}': {e}")
            return False

    def deletar_arquivo(self, bucket_name: str, object_name: str) -> bool:
        """Remove um objeto específico de dentro do bucket."""
        try:
            self.s3_client.delete_object(Bucket=bucket_name, Key=object_name)
            logger.info(f"Objeto '{object_name}' deletado de '{bucket_name}'.")
            return True
        except Exception as e:
            logger.error(f"Erro ao deletar '{object_name}': {e}")
            return False

    def gerar_url_presassinada(self, bucket_name: str, object_name: str, expiration: int = 3600) -> Optional[str]:
        """Gera uma URL temporária e assinada para acesso seguro a um objeto privado."""
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket_name, 'Key': object_name},
                ExpiresIn=expiration
            )
            logger.info(f"URL pré-assinada gerada para '{object_name}' (validade: {expiration}s).")
            return url
        except Exception as e:
            logger.error(f"Erro ao gerar URL pré-assinada para '{object_name}': {e}")
            return None

    # =========================================================================
    # EVOLUÇÕES S3: MEMÓRIA RAM, PREFIXOS, EXISTÊNCIA E METADADOS/TAGS
    # =========================================================================

    def enviar_conteudo_texto(
        self,
        conteudo: str,
        bucket_name: str,
        object_name: str,
        metadata: Optional[Dict[str, str]] = None,
        content_type: str = "text/plain; charset=utf-8"
    ) -> bool:
        """Envia uma string (logs, JSON, relatórios da IA) direto da memória RAM para o S3."""
        try:
            kwargs = {
                "Bucket": bucket_name,
                "Key": object_name,
                "Body": conteudo.encode("utf-8"),
                "ContentType": content_type
            }
            if metadata:
                kwargs["Metadata"] = metadata

            self.s3_client.put_object(**kwargs)
            logger.info(f"Conteúdo em memória gravado em '{bucket_name}/{object_name}'.")
            return True
        except Exception as e:
            logger.error(f"Erro ao gravar conteúdo em memória em '{object_name}': {e}")
            return False

    def ler_conteudo_texto(self, bucket_name: str, object_name: str) -> Optional[str]:
        """Lê o conteúdo de um objeto do S3 diretamente para uma string na memória RAM."""
        try:
            response = self.s3_client.get_object(Bucket=bucket_name, Key=object_name)
            texto = response["Body"].read().decode("utf-8")
            logger.info(f"Conteúdo de '{object_name}' lido para memória ({len(texto)} caracteres).")
            return texto
        except ClientError as e:
            logger.error(f"Erro AWS ao ler '{object_name}': {e.response['Error']['Message']}")
            return None
        except Exception as e:
            logger.error(f"Erro inesperado ao ler '{object_name}': {e}")
            return None

    def listar_arquivos(self, bucket_name: str, prefixo: str = "") -> List[str]:
        """Lista chaves de objetos no bucket, filtrando opcionalmente por prefixo (ex: 'logs/')."""
        try:
            response = self.s3_client.list_objects_v2(Bucket=bucket_name, Prefix=prefixo)
            objetos = [item["Key"] for item in response.get("Contents", [])]
            logger.info(f"Listagem em '{bucket_name}' (prefixo='{prefixo}'): {len(objetos)} objeto(s).")
            return objetos
        except Exception as e:
            logger.error(f"Erro ao listar objetos com prefixo '{prefixo}': {e}")
            return []

    def arquivo_existe(self, bucket_name: str, object_name: str) -> bool:
        """Verifica de forma leve (HEAD request) se um objeto existe no bucket."""
        try:
            self.s3_client.head_object(Bucket=bucket_name, Key=object_name)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] in ("404", "NoSuchKey"):
                return False
            logger.error(f"Erro AWS ao verificar existência de '{object_name}': {e}")
            return False

    def obter_metadados(self, bucket_name: str, object_name: str) -> Optional[Dict[str, str]]:
        """Recupera os metadados customizados gravados no cabeçalho do objeto."""
        try:
            response = self.s3_client.head_object(Bucket=bucket_name, Key=object_name)
            return response.get("Metadata", {})
        except Exception as e:
            logger.error(f"Erro ao obter metadados de '{object_name}': {e}")
            return None

    def definir_tags(self, bucket_name: str, object_name: str, tags: Dict[str, str]) -> bool:
        """Aplica ou atualiza tags dinâmicas em um objeto existente no S3."""
        try:
            tag_set = [{"Key": k, "Value": v} for k, v in tags.items()]
            self.s3_client.put_object_tagging(
                Bucket=bucket_name,
                Key=object_name,
                Tagging={"TagSet": tag_set}
            )
            logger.info(f"Tags aplicadas em '{object_name}': {tags}")
            return True
        except Exception as e:
            logger.error(f"Erro ao aplicar tags em '{object_name}': {e}")
            return False

    def obter_tags(self, bucket_name: str, object_name: str) -> Dict[str, str]:
        """Lê as tags associadas a um objeto no S3."""
        try:
            response = self.s3_client.get_object_tagging(Bucket=bucket_name, Key=object_name)
            return {t["Key"]: t["Value"] for t in response.get("TagSet", [])}
        except Exception as e:
            logger.error(f"Erro ao ler tags de '{object_name}': {e}")
            return {}

# =========================================================================
    # OPERAÇÕES DYNAMODB: HISTÓRICO ESTRUTURADO DE INCIDENTES
    # =========================================================================

    def criar_tabela_incidentes(self, table_name: str = "net-ai-incidentes") -> bool:
        """Cria a tabela NoSQL no DynamoDB para armazenar o histórico de incidentes."""
        try:
            self.dynamodb_client.create_table(
                TableName=table_name,
                KeySchema=[
                    {'AttributeName': 'incidente_id', 'KeyType': 'HASH'}  # Partition Key
                ],
                AttributeDefinitions=[
                    {'AttributeName': 'incidente_id', 'AttributeType': 'S'}  # String
                ],
                BillingMode='PAY_PER_REQUEST'
            )
            logger.info(f"Tabela DynamoDB '{table_name}' criada com sucesso.")
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceInUseException':
                logger.info(f"Tabela DynamoDB '{table_name}' já existe.")
                return True
            logger.error(f"Erro AWS ao criar tabela '{table_name}': {e.response['Error']['Message']}")
            return False
        except Exception as e:
            logger.error(f"Erro inesperado ao criar tabela '{table_name}': {e}")
            return False

    def registrar_incidente(
        self,
        table_name: str,
        incidente_id: str,
        equipamento: str,
        severidade: str,
        diagnostico_ia: str,
        s3_key: str,
        status: str = "PENDENTE"
    ) -> bool:
        """Insere um novo registro estruturado de incidente no DynamoDB."""
        try:
            self.dynamodb_client.put_item(
                TableName=table_name,
                Item={
                    'incidente_id': {'S': incidente_id},
                    'equipamento': {'S': equipamento},
                    'severidade': {'S': severidade},
                    'diagnostico_ia': {'S': diagnostico_ia},
                    's3_key': {'S': s3_key},
                    'status': {'S': status}
                }
            )
            logger.info(f"Incidente '{incidente_id}' registrado no DynamoDB (equipamento: {equipamento}).")
            return True
        except Exception as e:
            logger.error(f"Erro ao registrar incidente '{incidente_id}': {e}")
            return False

    def buscar_incidente(self, table_name: str, incidente_id: str) -> Optional[Dict[str, Any]]:
        """Busca um incidente específico pela chave primária e converte para dict Python limpo."""
        try:
            response = self.dynamodb_client.get_item(
                TableName=table_name,
                Key={'incidente_id': {'S': incidente_id}}
            )
            item = response.get('Item')
            if not item:
                logger.warning(f"Incidente '{incidente_id}' não encontrado na tabela '{table_name}'.")
                return None

            # Converte o formato tipado do DynamoDB ({'S': 'valor'}) para dicionário padrão
            dados_limpos = {k: list(v.values())[0] for k, v in item.items()}
            logger.info(f"Incidente '{incidente_id}' recuperado com sucesso.")
            return dados_limpos
        except Exception as e:
            logger.error(f"Erro ao buscar incidente '{incidente_id}': {e}")
            return None

    def atualizar_status_incidente(self, table_name: str, incidente_id: str, novo_status: str) -> bool:
        """Atualiza o status de um incidente (ex: PENDENTE -> REMEDIADO)."""
        try:
            self.dynamodb_client.update_item(
                TableName=table_name,
                Key={'incidente_id': {'S': incidente_id}},
                UpdateExpression="SET #st = :val",
                ExpressionAttributeNames={'#st': 'status'},  # 'status' é palavra reservada no DynamoDB
                ExpressionAttributeValues={':val': {'S': novo_status}}
            )
            logger.info(f"Status do incidente '{incidente_id}' atualizado para '{novo_status}'.")
            return True
        except Exception as e:
            logger.error(f"Erro ao atualizar status do incidente '{incidente_id}': {e}")
            return False

    # =========================================================================
    # OPERAÇÕES SECRETS MANAGER: COFRE DE CREDENCIAIS E CHAVES DE API
    # =========================================================================

    def criar_segredo(self, nome_segredo: str, segredo_dict: Dict[str, str], descricao: str = "") -> bool:
        """Cria um novo segredo (dicionário convertido em JSON) no cofre da AWS."""
        try:
            self.secrets_client.create_secret(
                Name=nome_segredo,
                Description=descricao,
                SecretString=json.dumps(segredo_dict)
            )
            logger.info(f"Segredo '{nome_segredo}' guardado com sucesso no cofre.")
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceExistsException':
                logger.warning(f"Segredo '{nome_segredo}' já existe no cofre.")
                return False
            logger.error(f"Erro AWS ao criar segredo '{nome_segredo}': {e.response['Error']['Message']}")
            return False
        except Exception as e:
            logger.error(f"Erro inesperado ao criar segredo '{nome_segredo}': {e}")
            return False

    def buscar_segredo(self, nome_segredo: str) -> Optional[Dict[str, str]]:
        """Recupera um segredo do cofre e o converte de volta para dicionário Python."""
        try:
            response = self.secrets_client.get_secret_value(SecretId=nome_segredo)
            segredo_str = response.get('SecretString')
            if not segredo_str:
                return None

            logger.info(f"Segredo '{nome_segredo}' recuperado do cofre em memória.")
            return json.loads(segredo_str)
        except ClientError as e:
            logger.error(f"Erro AWS ao buscar segredo '{nome_segredo}': {e.response['Error']['Message']}")
            return None
        except Exception as e:
            logger.error(f"Erro inesperado ao buscar segredo '{nome_segredo}': {e}")
            return None

    def atualizar_segredo(self, nome_segredo: str, novos_dados_dict: Dict[str, str]) -> bool:
        """Atualiza o valor de um segredo já existente no cofre."""
        try:
            self.secrets_client.put_secret_value(
                SecretId=nome_segredo,
                SecretString=json.dumps(novos_dados_dict)
            )
            logger.info(f"Segredo '{nome_segredo}' atualizado com sucesso.")
            return True
        except Exception as e:
            logger.error(f"Erro ao atualizar segredo '{nome_segredo}': {e}")
            return False

    def gerar_senha_forte(self, tamanho: int = 20) -> str:
        """Gera uma senha aleatória criptograficamente segura (letras, números e símbolos)."""
        alfabeto = string.ascii_letters + string.digits + "!@#$%&*-_=+"
        senha = ''.join(secrets.choice(alfabeto) for _ in range(tamanho))
        logger.info(f"Nova senha segura gerada ({tamanho} caracteres).")
        return senha


    # =========================================================================
    # OPERAÇÕES SQS: FILA DE ALERTAS DE REDE
    # =========================================================================

    def criar_fila(self, nome_fila: str = "net-ai-alertas-queue") -> Optional[str]:
        """Cria uma fila no SQS e retorna a URL dela."""
        try:
            response = self.sqs_client.create_queue(QueueName=nome_fila)
            queue_url = response.get('QueueUrl')
            logger.info(f"Fila SQS '{nome_fila}' pronta. URL: {queue_url}")
            return queue_url
        except Exception as e:
            logger.error(f"Erro ao criar fila SQS '{nome_fila}': {e}")
            return None


    def enviar_alerta_fila(self, queue_url: str, evento_dict: Dict[str, Any]) -> bool:
        """Envia um evento de rede (dicionário convertido em JSON) para a fila."""
        try:
            self.sqs_client.send_message(
                QueueUrl=queue_url,
                MessageBody=json.dumps(evento_dict)
            )
            logger.info(f"Alerta do equipamento '{evento_dict.get('equipamento')}' enviado para a fila.")
            return True
        except Exception as e:
            logger.error(f"Erro ao enviar mensagem para a fila SQS: {e}")
            return False
        

    def consumir_alertas_fila(self, queue_url: str, max_mensagens: int = 5) -> List[Dict[str, Any]]:
        """Lê os alertas pendentes na fila, converte de volta para dict e apaga da fila."""
        eventos_processados: List[Dict[str, Any]] = []
        try:
            response = self.sqs_client.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=max_mensagens,
                WaitTimeSeconds=2  # Long Polling: espera até 2s se a fila estiver vazia
            )

            mensagens = response.get('Messages', [])
            if not mensagens:
                logger.info("Nenhum alerta pendente na fila SQS.")
                return []

            for msg in mensagens:
                corpo_dict = json.loads(msg['Body'])
                eventos_processados.append(corpo_dict)

                # Confirma o recebimento apagando a mensagem da fila pelo ReceiptHandle
                self.sqs_client.delete_message(
                    QueueUrl=queue_url,
                    ReceiptHandle=msg['ReceiptHandle']
                )

            logger.info(f"{len(eventos_processados)} alerta(s) consumido(s) e removido(s) da fila.")
            return eventos_processados
        except Exception as e:
            logger.error(f"Erro ao consumir mensagens da fila SQS: {e}")
            return []

    # =========================================================================
    # OPERAÇÕES SNS: DISPARO DE NOTIFICAÇÕES E ALERTAS CRÍTICOS
    # =========================================================================

    def criar_topico_alertas(self, nome_topico: str = "net-ai-alertas-criticos") -> Optional[str]:
        """Cria um canal (Tópico) no SNS para alertas críticos e retorna o TopicArn."""
        try:
            response = self.sns_client.create_topic(Name=nome_topico)
            topic_arn = response.get('TopicArn')
            logger.info(f"Tópico SNS '{nome_topico}' pronto. ARN: {topic_arn}")
            return topic_arn
        except Exception as e:
            logger.error(f"Erro ao criar tópico SNS '{nome_topico}': {e}")
            return None

    def inscrever_alerta(self, topic_arn: str, protocolo: str, endpoint: str) -> Optional[str]:
        """Inscreve um destino (ex: 'email', 'https', 'sqs') no tópico SNS."""
        try:
            response = self.sns_client.subscribe(
                TopicArn=topic_arn,
                Protocol=protocolo,
                Endpoint=endpoint
            )
            sub_arn = response.get('SubscriptionArn')
            logger.info(f"Inscrição realizada no tópico ({protocolo} -> {endpoint}).")
            return sub_arn
        except Exception as e:
            logger.error(f"Erro ao inscrever '{endpoint}' no tópico SNS: {e}")
            return None

    def disparar_alerta_critico(self, topic_arn: str, assunto: str, mensagem: str) -> Optional[str]:
        """Publica um alerta no tópico SNS para notificar todos os inscritos."""
        try:
            response = self.sns_client.publish(
                TopicArn=topic_arn,
                Subject=assunto[:100],  # A AWS limita o assunto de e-mail SNS a 100 caracteres
                Message=mensagem
            )
            msg_id = response.get('MessageId')
            logger.info(f"Alerta crítico disparado via SNS! MessageId: {msg_id}")
            return msg_id
        except Exception as e:
            logger.error(f"Erro ao disparar alerta no SNS: {e}")
            return None