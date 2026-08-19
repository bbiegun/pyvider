import sys

filename = "src/pyvider/protocols/tfprotov6/handlers/open_ephemeral_resource.py"
with open(filename, 'r') as f:
    content = f.read()

content = content.replace("from pyvider.exceptions import PyviderError", "from pyvider.exceptions import PyviderError, Deferral")

deferral_catch = """    except Deferral as e:
        logger.info("Response deferred", operation="open_ephemeral_resource", resource_type=request.type_name, reason=e.reason.name)
        if not getattr(request.client_capabilities, "deferral_allowed", False):
            diag = pb.Diagnostic(
                severity=pb.Diagnostic.ERROR,
                summary="Invalid Deferral",
                detail="The provider raised a Deferral but Terraform did not set deferral_allowed for this request."
            )
            response.diagnostics.append(diag)
        else:
            response.deferred.reason = pb.Deferred.Reason.Value(e.reason.name)
    except (CtyValidationError, PyviderError) as e:"""

content = content.replace("    except (CtyValidationError, PyviderError) as e:", deferral_catch)

with open(filename, 'w') as f:
    f.write(content)
