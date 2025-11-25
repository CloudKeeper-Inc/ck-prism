# CK-Prism-CLI - Authentication for AWS Credentials

Authenticates users via CloudKeeper Prism and exchanges tokens for AWS credentials.

## Operating System Support
- `macOS`
- `Linux`
- `WSL on Windows`
- `Windows`

## Python Support
**Python 3.6 and above**

## Prerequisites

### Software Prerequisites
- Python 3.6 or above
- AWS CLI v2 (optional, for using credentials)

## Installation

```bash
pip3 install ck-prism
```

Verify installation:
```bash
ck-prism help
```

If command not found, add Python packages folder to PATH:
- Linux: `/home/{username}/.local/bin`
- macOS: `/Users/{username}/Library/Python/{Python Version}/bin`

## Configuration

### Interactive Configuration
```bash
ck-prism configure
```

You'll be prompted for:
- **Prism Domain**: This can be found in your Prism instance - "https://prism.cloudkeeper.com" , "https://myprism.xyz.in"
- **Prism Tenant**: This can be found in your Prism SSO Url - "https://sso.prism.cloudkeeper.com' here, 'sso' is your Prism tenant
- **AWS Region**: Default is `us-east-1`

### Manual Configuration
Edit `~/.ck-prism/config.json`:

```json
{
  "default": {
    "realm": "cloudkeeper",
    "client_id": "ckauth-cli",
    "region": "us-east-1",
    "output": "json",
    "role_arn": "arn:aws:iam::123456789012:role/CKAuth-Admin,arn:aws:iam::123456789012:saml-provider/CKAuthProvider",
    "account_id": "123456789012",
    "role_name": "CKAuth-Admin"
  }
}
```

### Named Profiles
```bash
ck-prism configure --profile production
```

## Usage

### Default Profile
```bash
ck-prism login
```

### Named Profile
```bash
ck-prism login --profile production
```

The tool will:
1. Check for cached tokens
2. Refresh expired tokens automatically
3. Open browser for initial authentication (if needed)
4. Exchange token for AWS credentials
5. Write credentials to `~/.aws/credentials`

### Using AWS Credentials
After login, use AWS CLI normally:
```bash
aws s3 ls
aws ec2 describe-instances
```

Or with named profile:
```bash
aws s3 ls --profile production
```

## Token Caching

Tokens are cached in `~/.ck-prism/tokens/` and automatically refreshed when needed.

## Troubleshooting

- **Command not found**: Ensure Python packages directory is in PATH
- **Authentication failed**: Re-run `ck-prism login`
- **Expired credentials**: Run `ck-prism login` again to refresh