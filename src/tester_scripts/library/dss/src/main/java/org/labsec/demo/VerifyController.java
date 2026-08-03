package org.labsec.demo;

import eu.europa.esig.dss.model.DSSDocument;
import eu.europa.esig.dss.model.InMemoryDocument;
import eu.europa.esig.dss.model.policy.ValidationPolicy;
import eu.europa.esig.dss.model.x509.CertificateToken;
import eu.europa.esig.dss.policy.ValidationPolicyFacade;
import eu.europa.esig.dss.simplereport.SimpleReport;
import eu.europa.esig.dss.spi.DSSUtils;
import eu.europa.esig.dss.spi.validation.CertificateVerifier;
import eu.europa.esig.dss.spi.validation.CommonCertificateVerifier;
import eu.europa.esig.dss.spi.x509.CommonTrustedCertificateSource;
import eu.europa.esig.dss.validation.SignedDocumentValidator;
import eu.europa.esig.dss.validation.reports.Reports;
import java.io.InputStream;
import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

@RestController
@RequestMapping("/verify")
public class VerifyController {

        private static final Logger LOG = LoggerFactory.getLogger(
                        VerifyController.class);

        private CertificateVerifier getCertificateVerifier() {
                CommonTrustedCertificateSource trustedCertificateSource = new CommonTrustedCertificateSource();
                for (int i = 1; i <= 7; ++i) {
                        InputStream certStream = VerifyController.class.getClassLoader().getResourceAsStream(
                                        String.format("cert-%s.pem", i));
                        CertificateToken cert = DSSUtils.loadCertificate(certStream);
                        trustedCertificateSource.addCertificate(cert);
                }

                CertificateVerifier cv = new CommonCertificateVerifier();
                cv.addTrustedCertSources(trustedCertificateSource);
                return cv;
        }

        private ValidationPolicy getValidationPolicy() throws Exception {
                return ValidationPolicyFacade.newFacade().getValidationPolicy(
                                VerifyController.class.getClassLoader().getResourceAsStream(
                                                "constraints.xml"));
        }

        private void logDssSignatureDiagnostic(Reports reports) {
                for (var signature : reports.getDiagnosticData().getAllSignatures()) {
                        LOG.info("---------------REVISION----------------");
                        LOG.info("| FieldName {}", signature.getFirstFieldName());
                        LOG.info("| Indication {}", reports.getSimpleReport().getIndication(signature.getId()));
                        LOG.info("| Subindication {}", reports.getSimpleReport().getSubIndication(signature.getId()));
                        for (var m : reports.getSimpleReport().getAdESValidationErrors(signature.getId())) {
                                LOG.info("ADES ERRO => {}", m.getValue());
                        }

                        if (signature.getPdfExtensionChanges() != null) {
                                LOG.info("Extension Modifications");
                                for (var om : signature.getPdfExtensionChanges()) {
                                        LOG.info("| {}, {}, {}", om.getAction(), om.getType(), om.getValue());
                                }
                        }
                        if (signature.getPdfUndefinedChanges() != null) {

                                LOG.info("Undefined Modifications");
                                for (var om : signature.getPdfUndefinedChanges()) {
                                        LOG.info("| {}, {}, {}", om.getAction(), om.getType(), om.getValue());
                                }
                        }
                        if (signature.getPdfAnnotationChanges() != null) {

                                LOG.info("Annotation Modifications");
                                for (var om : signature.getPdfAnnotationChanges()) {
                                        LOG.info("| {}, {}, {}", om.getAction(), om.getType(), om.getValue());
                                }
                        }
                        if (signature.getPdfSignatureOrFormFillChanges() != null) {

                                LOG.info("Signature Form Fill Modifications");
                                for (var om : signature.getPdfSignatureOrFormFillChanges()) {
                                        LOG.info("| {}, {}, {}", om.getAction(), om.getType(), om.getValue());
                                }
                        }
                        if (signature.getPDFRevision() != null
                                        && signature.getPDFRevision().getModifiedFieldNames() != null) {
                                LOG.info("Changed Fields");
                                for (var om : signature.getPDFRevision().getModifiedFieldNames()) {
                                        LOG.info("| {}", om);
                                }
                        }
                        if (signature.getPdfAnnotationsOverlapConcernedPages() != null) {

                                LOG.info("Overlapping Modifications");
                                for (var om : signature.getPdfAnnotationsOverlapConcernedPages()) {
                                        LOG.info("| Page {}", om);
                                }
                        }
                }

        }

        @PostMapping
        public ResponseEntity<Map<String, Object>> verifyFile(
                        @RequestParam("file") MultipartFile file) throws Exception {
                DSSDocument signedFile = new InMemoryDocument(
                                file.getBytes(),
                                file.getOriginalFilename());
                var cv = getCertificateVerifier();

                var validator = SignedDocumentValidator.fromDocument(signedFile);
                validator.setCertificateVerifier(cv);

                Reports reports = validator.validateDocument(getValidationPolicy());
                logDssSignatureDiagnostic(reports);

                SimpleReport simpleReport = reports.getSimpleReport();

                boolean allSignaturesValid = simpleReport
                                .getSignatureIdList()
                                .stream()
                                .allMatch(sigId -> simpleReport.isValid(sigId));

                boolean hasWarnings = simpleReport
                                .getSignatureIdList()
                                .stream()
                                .anyMatch(sigId -> !simpleReport.getAdESValidationWarnings(sigId).isEmpty());

                String verdict = allSignaturesValid ? "VALID" : "INVALID";
                return ResponseEntity.ok(Map.of("result", verdict, "warn_modified", hasWarnings));
        }
}
