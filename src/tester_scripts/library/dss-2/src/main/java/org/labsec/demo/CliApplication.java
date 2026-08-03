package org.labsec.demo;

import eu.europa.esig.dss.jaxb.object.Message;
import eu.europa.esig.dss.model.DSSDocument;
import eu.europa.esig.dss.model.FileDocument;
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

import java.io.File;
import java.io.InputStream;
import java.util.List;

public class CliApplication {

    public static void main(String[] args) {
        if (args.length < 1) {
            System.err.println("Usage: java -jar dss-2.jar <pdf-file-path>");
            System.exit(1);
        }

        String filePath = args[0];
        File file = new File(filePath);

        try {
            DSSDocument signedFile = new FileDocument(file);
            CertificateVerifier cv = getCertificateVerifier();

            SignedDocumentValidator validator = SignedDocumentValidator.fromDocument(signedFile);
            validator.setCertificateVerifier(cv);

            Reports reports = validator.validateDocument(getValidationPolicy());
            SimpleReport simpleReport = reports.getSimpleReport();

            System.out.println("Verification details:");
            for (var signature : reports.getDiagnosticData().getAllSignatures()) {
                String sigId = signature.getId();
                System.out.println("--------------- SIGNATURE: " + sigId + " ----------------");
                System.out.println("| FieldName: " + signature.getFirstFieldName());
                System.out.println("| Indication: " + simpleReport.getIndication(sigId));
                System.out.println("| Subindication: " + simpleReport.getSubIndication(sigId));

                List<Message> errors = simpleReport.getAdESValidationErrors(sigId);
                if (errors != null && !errors.isEmpty()) {
                    System.out.println("| ADES Validation Errors:");
                    for (var error : errors) {
                        System.out.println("  - " + error.getValue());
                    }
                }

                List<Message> warnings = simpleReport.getAdESValidationWarnings(sigId);
                if (warnings != null && !warnings.isEmpty()) {
                    System.out.println("| ADES Validation Warnings:");
                    for (var warning : warnings) {
                        System.out.println("  - " + warning.getValue());
                    }
                }

                if (signature.getPdfExtensionChanges() != null && !signature.getPdfExtensionChanges().isEmpty()) {
                    System.out.println("| Extension Modifications:");
                    for (var om : signature.getPdfExtensionChanges()) {
                        System.out.println("  - Action: " + om.getAction() + ", Type: " + om.getType() + ", Value: "
                                + om.getValue());
                    }
                }
                if (signature.getPdfUndefinedChanges() != null && !signature.getPdfUndefinedChanges().isEmpty()) {
                    System.out.println("| Undefined Modifications:");
                    for (var om : signature.getPdfUndefinedChanges()) {
                        System.out.println("  - Action: " + om.getAction() + ", Type: " + om.getType() + ", Value: "
                                + om.getValue());
                    }
                }
                if (signature.getPdfAnnotationChanges() != null && !signature.getPdfAnnotationChanges().isEmpty()) {
                    System.out.println("| Annotation Modifications:");
                    for (var om : signature.getPdfAnnotationChanges()) {
                        System.out.println("  - Action: " + om.getAction() + ", Type: " + om.getType() + ", Value: "
                                + om.getValue());
                    }
                }
                if (signature.getPdfSignatureOrFormFillChanges() != null
                        && !signature.getPdfSignatureOrFormFillChanges().isEmpty()) {
                    System.out.println("| Signature Form Fill Modifications:");
                    for (var om : signature.getPdfSignatureOrFormFillChanges()) {
                        System.out.println("  - Action: " + om.getAction() + ", Type: " + om.getType() + ", Value: "
                                + om.getValue());
                    }
                }
                if (signature.getPDFRevision() != null && signature.getPDFRevision().getModifiedFieldNames() != null) {
                    System.out.println("| Changed Fields:");
                    for (var field : signature.getPDFRevision().getModifiedFieldNames()) {
                        System.out.println("  - " + field);
                    }
                }
                if (signature.getPdfAnnotationsOverlapConcernedPages() != null
                        && !signature.getPdfAnnotationsOverlapConcernedPages().isEmpty()) {
                    System.out.println("| Overlapping Modifications:");
                    for (var page : signature.getPdfAnnotationsOverlapConcernedPages()) {
                        System.out.println("  - Page: " + page);
                    }
                }
            }

            System.out.println("----------------------------------------");
            boolean allSignaturesValid = simpleReport
                    .getSignatureIdList()
                    .stream()
                    .allMatch(sigId -> simpleReport.isValid(sigId));
            System.out.println("IS VALID: " + allSignaturesValid);
        } catch (Exception e) {
            System.err.println("Verification failed due to an exception:");
            e.printStackTrace();
            System.exit(1);
        }
        System.exit(0);
    }

    private static CertificateVerifier getCertificateVerifier() {
        CommonTrustedCertificateSource trustedCertificateSource = new CommonTrustedCertificateSource();
        for (int i = 1; i <= 2; ++i) {
            InputStream certStream = CliApplication.class.getClassLoader().getResourceAsStream(
                    String.format("cert-%s.pem", i));
            CertificateToken cert = DSSUtils.loadCertificate(certStream);
            trustedCertificateSource.addCertificate(cert);
        }

        CertificateVerifier cv = new CommonCertificateVerifier();
        cv.addTrustedCertSources(trustedCertificateSource);
        return cv;
    }

    private static ValidationPolicy getValidationPolicy() throws Exception {
        return ValidationPolicyFacade.newFacade().getValidationPolicy(
                CliApplication.class.getClassLoader().getResourceAsStream(
                        "constraints.xml"));
    }
}
