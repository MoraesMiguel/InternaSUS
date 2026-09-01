#################################################################################
# GLOBALS                                                                       #
#################################################################################

PROJECT_NAME = internasus
PYTHON_VERSION = 3.12
PYTHON_INTERPRETER = python

#################################################################################
# COMMANDS                                                                      #
#################################################################################


## Install Python dependencies
.PHONY: requirements
requirements:
	uv sync
	



## Delete all compiled Python files
.PHONY: clean
clean:
	find . -type f -name "*.py[co]" -delete
	find . -type d -name "__pycache__" -delete


## Lint using ruff (use `make format` to do formatting)
.PHONY: lint
lint:
	ruff format --check
	ruff check

## Format source code with ruff
.PHONY: format
format:
	ruff check --fix
	ruff format





## Set up Python interpreter environment
.PHONY: create_environment
create_environment:
	uv venv --python $(PYTHON_VERSION)
	@echo ">>> New uv virtual environment created. Activate with:"
	@echo ">>> Windows: .\\\\.venv\\\\Scripts\\\\activate"
	@echo ">>> Unix/macOS: source ./.venv/bin/activate"
	



#################################################################################
# PROJECT RULES                                                                 #
#################################################################################


## Executa a ingestao completa (CNES + SIA + SIH + SIDRA) para data/raw/
.PHONY: data
data: requirements
	$(PYTHON_INTERPRETER) -m internasus.dataset ingest-all

## Executa apenas a ingestao do CNES
.PHONY: ingest-cnes
ingest-cnes:
	$(PYTHON_INTERPRETER) -m internasus.dataset ingest-cnes

## Executa apenas a ingestao do SIA
.PHONY: ingest-sia
ingest-sia:
	$(PYTHON_INTERPRETER) -m internasus.dataset ingest-sia

## Executa apenas a ingestao do SIH
.PHONY: ingest-sih
ingest-sih:
	$(PYTHON_INTERPRETER) -m internasus.dataset ingest-sih

## Executa apenas a ingestao do IBGE/SIDRA
.PHONY: ingest-sidra
ingest-sidra:
	$(PYTHON_INTERPRETER) -m internasus.dataset ingest-sidra

## Baixa a tabela oficial CID-10 (referencia estatica) para data/external/
.PHONY: ingest-cid10
ingest-cid10:
	$(PYTHON_INTERPRETER) -m internasus.dataset ingest-cid10

## Gera a camada Silver a partir de data/raw/
.PHONY: silver
silver:
	$(PYTHON_INTERPRETER) -m internasus.processing.silver

## Gera a camada Gold (star schema) a partir de data/silver/
.PHONY: gold
gold:
	$(PYTHON_INTERPRETER) -m internasus.processing.gold

## Envia data/raw/ para o bucket Bronze no OCI
.PHONY: publish-raw
publish-raw:
	$(PYTHON_INTERPRETER) -m internasus.oci_storage publish-raw

## Envia data/silver/ para o bucket Silver no OCI
.PHONY: publish-silver
publish-silver:
	$(PYTHON_INTERPRETER) -m internasus.oci_storage publish-silver

## Envia data/gold/ para o bucket Gold no OCI
.PHONY: publish-gold
publish-gold:
	$(PYTHON_INTERPRETER) -m internasus.oci_storage publish-gold

## Envia data/raw/, data/silver/ e data/gold/ para os respectivos buckets no OCI
.PHONY: publish-all
publish-all:
	$(PYTHON_INTERPRETER) -m internasus.oci_storage publish-all

## Roda o dashboard Streamlit localmente (le data/gold/ local)
.PHONY: dashboard
dashboard:
	streamlit run dashboard/Home.py

## Roda a suite de testes unitarios (rapida, sem rede)
.PHONY: test
test:
	pytest

## Roda os testes de integracao reais (rede, mais lento)
.PHONY: test-integration
test-integration:
	pytest -m integration


#################################################################################
# Self Documenting Commands                                                     #
#################################################################################

.DEFAULT_GOAL := help

define PRINT_HELP_PYSCRIPT
import re, sys; \
lines = '\n'.join([line for line in sys.stdin]); \
matches = re.findall(r'\n## (.*)\n[\s\S]+?\n([a-zA-Z_-]+):', lines); \
print('Available rules:\n'); \
print('\n'.join(['{:25}{}'.format(*reversed(match)) for match in matches]))
endef
export PRINT_HELP_PYSCRIPT

help:
	@$(PYTHON_INTERPRETER) -c "${PRINT_HELP_PYSCRIPT}" < $(MAKEFILE_LIST)
