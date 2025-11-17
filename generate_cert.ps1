# Generate self-signed certificate for localhost
$cert = New-SelfSignedCertificate `
    -DnsName "localhost" `
    -CertStoreLocation "Cert:\CurrentUser\My" `
    -KeyAlgorithm RSA `
    -KeyLength 2048 `
    -NotAfter (Get-Date).AddYears(10)

# Export certificate
$certPath = ".\localhost.crt"
$keyPath = ".\localhost.key"

$certPassword = ConvertTo-SecureString -String "chainlit" -Force -AsPlainText

Export-PfxCertificate -Cert $cert -FilePath ".\localhost.pfx" -Password $certPassword

Write-Host "✅ Certificate created: localhost.pfx (password: chainlit)"
Write-Host "Certificate Thumbprint: $($cert.Thumbprint)"
