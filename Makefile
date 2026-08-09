.PHONY: package verify clean

# Assemble the self-contained on-prem package into dist/obserra-sap-uac
package:
	python scripts/assemble_onprem.py dist

# Build the on-prem Docker images — proves the one-click installer boots (needs Docker)
verify: package
	cd dist/obserra-sap-uac && docker compose -f deploy/docker-compose.yml build

clean:
	rm -rf dist
