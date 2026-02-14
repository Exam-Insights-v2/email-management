# Microsoft SSO Setup Guide

This guide walks you through setting up Microsoft Single Sign-On (SSO) for user authentication and email access in EmailIQ.

## Prerequisites

- A Microsoft account (personal or organisational)
- Access to Azure Portal (portal.azure.com)
- Your application domain name (for production redirect URIs)

## Step 1: Register Your Application in Azure AD

1. **Go to Azure Portal**
   - Navigate to [https://portal.azure.com](https://portal.azure.com)
   - Sign in with your Microsoft account

2. **Access Azure Active Directory**
   - In the search bar at the top, type "Azure Active Directory" or "Microsoft Entra ID"
   - Click on "Azure Active Directory" or "Microsoft Entra ID" from the results

3. **Create App Registration**
   - Click on "App registrations" in the left sidebar
   - Click the "+ New registration" button at the top

4. **Configure App Registration**
   - **Name**: Enter a name for your app (e.g., "EmailIQ")
   - **Supported account types**: Choose one of the following:
     - **"Any Entra ID Tenant + Personal Microsoft accounts"** ⭐ **Recommended** - Allows users from any organisation AND personal Microsoft accounts (e.g., @outlook.com, @hotmail.com)
     - **"Multiple Entra ID tenants"** - Only allows users from other organisational directories (NOT personal accounts)
     - **"Single tenant only - Default Directory"** - Only allows users from your specific organisation
     - **"Personal accounts only"** - Only allows personal Microsoft accounts (NOT organisational accounts)
   - **Redirect URI**: Leave blank for now (we'll add this later)
   - Click **"Register"**

5. **Note Your Application Details**
   - After registration, you'll see the **Overview** page
   - Copy the **Application (client) ID** - you'll need this for `MICROSOFT_OAUTH_CLIENT_ID`
   - Note the **Directory (tenant) ID** - you'll need this for `MICROSOFT_OAUTH_TENANT_ID` (if using single tenant)

## Step 2: Create Client Secret

1. **Navigate to Certificates & Secrets**
   - In the left sidebar, click **"Certificates & secrets"**
   - Click **"+ New client secret"**

2. **Create Secret**
   - **Description**: Enter a description (e.g., "EmailIQ Production Secret")
   - **Expires**: Choose an expiration period (recommend 24 months for production)
   - Click **"Add"**

3. **Copy the Secret Value**
   - **IMPORTANT**: Copy the **Value** immediately - it will only be shown once!
   - This is your `MICROSOFT_OAUTH_CLIENT_SECRET`
   - Store it securely (you won't be able to see it again)

## Step 3: Configure Redirect URIs

1. **Navigate to Authentication**
   - In the left sidebar, click **"Authentication"**
   - Click **"+ Add a platform"**
   - Select **"Web"**

2. **Add Redirect URIs**
   Add the following redirect URIs (replace `email-iq.clarent.io` with your actual domain):

   **For User Login:**
   - `https://email-iq.clarent.io/auth/microsoft/callback/`
   - `http://localhost:8000/auth/microsoft/callback/` (for local development)

   **For Email Account Connection:**
   - `https://email-iq.clarent.io/accounts/microsoft/callback/`
   - `http://localhost:8000/accounts/microsoft/callback/` (for local development)

3. **Configure Implicit Grant (if needed)**
   - Under "Implicit grant and hybrid flows", you typically don't need to enable anything
   - Click **"Configure"** to save

## Step 4: Configure API Permissions

1. **Navigate to API Permissions**
   - In the left sidebar, click **"API permissions"**
   - Click **"+ Add a permission"**

2. **Select Microsoft Graph**
   - Choose **"Microsoft Graph"**
   - Select **"Delegated permissions"**

3. **Add Required Permissions**
   Add the following permissions by checking the boxes:

   **For User Authentication:**
   - `openid` (usually added automatically)
   - `profile`
   - `email`
   - `User.Read`

   **For Email Access:**
   - `Mail.Read`
   - `Mail.ReadWrite`

   **For Token Refresh:**
   - `offline_access`

4. **Grant Admin Consent (if applicable)**
   - If you're using organisational accounts, click **"Grant admin consent for [Your Organisation]"**
   - This is required for organisational users to use the app
   - For personal Microsoft accounts, users will consent when they first log in

## Step 5: Set Environment Variables

Add the following environment variables to your `.env` file (for local development) and DigitalOcean App Platform (for production):

### Local Development (.env file)

```bash
# Microsoft OAuth Configuration
MICROSOFT_OAUTH_CLIENT_ID=your-client-id-here
MICROSOFT_OAUTH_CLIENT_SECRET=your-client-secret-here
MICROSOFT_OAUTH_TENANT_ID=common
```

### Production (DigitalOcean App Platform)

1. Go to your DigitalOcean App Platform dashboard
2. Navigate to your app → **Settings** → **App-Level Environment Variables**
3. Add the following variables:

   - **Key**: `MICROSOFT_OAUTH_CLIENT_ID`
     **Value**: Your Application (client) ID from Azure AD

   - **Key**: `MICROSOFT_OAUTH_CLIENT_SECRET`
     **Value**: Your client secret value from Azure AD

   - **Key**: `MICROSOFT_OAUTH_TENANT_ID`
     **Value**: 
     - `common` (for multi-tenant - allows any Microsoft account)
     - OR your Directory (tenant) ID (for single tenant - only your organisation)

## Step 6: Understanding Tenant ID Options

### Option 1: Multi-Tenant (Recommended)
- **Value**: `common`
- **Allows**: Any Microsoft account (personal or organisational)
- **Use case**: Public application accessible to anyone

### Option 2: Single Tenant
- **Value**: Your Directory (tenant) ID from Azure AD Overview
- **Allows**: Only accounts in your specific organisation
- **Use case**: Internal application for your organisation only

## Step 7: Test the Setup

### Test User Login

1. **Start your application** (locally or in production)
2. Navigate to the login page
3. Click **"Continue with Microsoft"**
4. You should be redirected to Microsoft's login page
5. Sign in with your Microsoft account
6. Grant permissions when prompted
7. You should be redirected back and logged in

### Test Email Account Connection

1. **Log in** to your application
2. Navigate to **Settings** → **Accounts**
3. Click **"Connect Microsoft Account"** or similar
4. Enter your email address
5. Click **"Connect"**
6. You should be redirected to Microsoft's consent page
7. Grant the requested permissions (Mail.Read, Mail.ReadWrite, etc.)
8. You should be redirected back and the account should be connected
9. The application should now be able to sync emails from this Microsoft account

## Troubleshooting

### Issue: "Invalid redirect URI"
- **Solution**: Ensure the redirect URIs in Azure AD exactly match your application URLs
- Check for trailing slashes - they must match exactly
- Verify you're using `https://` for production and `http://` for local development

### Issue: "Insufficient privileges"
- **Solution**: Ensure all required API permissions are added and admin consent is granted (for organisational accounts)
- Check that `offline_access` is included for token refresh

### Issue: "AADSTS50011: The reply URL specified in the request does not match"
- **Solution**: Double-check your redirect URIs in Azure AD match exactly what your application is sending
- Common issues:
  - Missing trailing slash
  - Wrong protocol (http vs https)
  - Wrong port number

### Issue: "Token exchange failed"
- **Solution**: 
  - Verify your `MICROSOFT_OAUTH_CLIENT_SECRET` is correct and hasn't expired
  - Check that your client secret hasn't been regenerated (old secrets become invalid)
  - Ensure your `MICROSOFT_OAUTH_CLIENT_ID` matches the Application ID in Azure AD

### Issue: "Cannot access emails"
- **Solution**:
  - Verify `Mail.Read` and `Mail.ReadWrite` permissions are added in Azure AD
  - Check that admin consent is granted (for organisational accounts)
  - Ensure the user granted consent when connecting their account
  - Check application logs for specific error messages

### Issue: "AADSTS50020: User account from identity provider does not exist in tenant"
- **What it means**: Your app registration's **Supported account types** setting doesn't allow the account you're trying to sign in with. This happens when:
  - You selected **"Single tenant only"** but are signing in with an account from a different organisation
  - You selected **"Multiple Entra ID tenants"** but are signing in with a personal Microsoft account (e.g., @outlook.com)
  - You selected **"Personal accounts only"** but are signing in with an organisational account
- **Solution**: Change your app registration to allow the account type you need:
  1. Go to [Azure Portal](https://portal.azure.com)
  2. Navigate to **Azure Active Directory** → **App registrations**
  3. Click on your app (e.g., "EmailIQ")
  4. Click **"Authentication"** in the left sidebar
  5. Under **"Supported account types"**, click **"Edit"**
  6. Select **"Any Entra ID Tenant + Personal Microsoft accounts"** (this allows both organisational and personal accounts)
  7. Click **"Save"**
  8. Also ensure your `MICROSOFT_OAUTH_TENANT_ID` environment variable is set to `common` (not a specific tenant ID)
- **Why this happens**: Each account type option restricts which users can sign in. For maximum compatibility, use **"Any Entra ID Tenant + Personal Microsoft accounts"**.

### Issue: "Property api.requestedAccessTokenVersion is invalid"
- **What it means**: The app manifest has an invalid or missing `requestedAccessTokenVersion` property. This can happen when changing account types or updating the app registration.
- **Solution**: Fix the access token version in the app manifest:
  1. Go to [Azure Portal](https://portal.azure.com)
  2. Navigate to **Azure Active Directory** → **App registrations**
  3. Click on your app (e.g., "EmailIQ")
  4. Click **"Manifest"** in the left sidebar (this opens a JSON editor)
  5. Look for the `"api"` section in the JSON
  6. Find or add the `"requestedAccessTokenVersion"` property
  7. Set it to `2` (for v2.0 tokens) - this is the recommended value:
     ```json
     "api": {
         "requestedAccessTokenVersion": 2
     }
     ```
  8. If the `"api"` section doesn't exist, add it at the root level of the manifest
  9. Click **"Save"** at the top
  10. After saving the manifest, try updating the **"Supported account types"** again
- **Why this happens**: Azure AD requires a valid token version setting. Setting it to `2` ensures you're using the latest v2.0 tokens which support all modern features.

### Issue: "Need admin approval" - Admin consent required for other organisations
- **What it means**: When your app is configured as multi-tenant (allowing users from any organisation), each organisation's administrator must grant consent **once** before their users can sign in. The permissions `Mail.Read` and `Mail.ReadWrite` require admin consent - this is a Microsoft security requirement that cannot be bypassed.
- **This is expected behaviour**: For multi-tenant apps, admin consent is required per organisation. This is by design to protect organisational email data.
- **Solution for other organisations**: Provide them with an admin consent URL. Each organisation's admin needs to visit this URL once:

  **Admin Consent URL Format:**
  ```
  https://login.microsoftonline.com/{their-tenant-id}/adminconsent?client_id={your-client-id}
  ```
  
  **Or use the common endpoint (works for any tenant):**
  ```
  https://login.microsoftonline.com/common/adminconsent?client_id={your-client-id}
  ```
  
  Replace `{your-client-id}` with your Application (client) ID (e.g., `630dfbe3-effb-465c-becf-b95e42e404fa`)
  
  **Example:**
  ```
  https://login.microsoftonline.com/common/adminconsent?client_id=630dfbe3-effb-465c-becf-b95e42e404fa
  ```

  **What happens:**
  1. Admin from the other organisation visits the URL
  2. They sign in with their admin account
  3. They see a consent screen asking to approve your app
  4. After approval, **all users** in that organisation can sign in without individual approval
  5. The consent is permanent (until revoked by an admin)

- **For your own organisation**: If you're an admin, you can grant consent directly:
  1. Go to [Azure Portal](https://portal.azure.com)
  2. Navigate to **Azure Active Directory** → **App registrations**
  3. Click on your app (e.g., "EmailIQ")
  4. Click **"API permissions"** in the left sidebar
  5. Click **"Grant admin consent for [Your Organisation Name]"** button at the top
  6. Click **"Yes"** to confirm

- **For personal Microsoft accounts**: Personal accounts (e.g., `@outlook.com`, `@hotmail.com`) can grant consent themselves and don't require admin approval.

- **Why this happens**: Microsoft protects organisational data by requiring administrators to approve apps that access sensitive resources like email. This is a security feature that cannot be disabled.

- **Important notes**:
  - Admin consent is required **once per organisation** - after that, all users in that organisation can use the app
  - You cannot bypass this requirement for organisational accounts
  - Personal Microsoft accounts can always consent themselves
  - Consider providing clear instructions to your users on how to request admin consent from their IT department

## Security Best Practices

1. **Never commit secrets to Git**
   - Keep `.env` in `.gitignore`
   - Use environment variables in production

2. **Rotate secrets regularly**
   - Set expiration dates on client secrets
   - Create new secrets before old ones expire
   - Update environment variables before deploying

3. **Use appropriate tenant configuration**
   - Use `common` for public applications
   - Use specific tenant ID for internal applications

4. **Monitor API usage**
   - Check Azure AD logs for suspicious activity
   - Set up alerts for unusual authentication patterns

## Summary Checklist

- [ ] Created Azure AD app registration
- [ ] Copied Application (client) ID
- [ ] Created and copied client secret
- [ ] Added redirect URIs (login and email connection)
- [ ] Added API permissions (openid, profile, email, User.Read, Mail.Read, Mail.ReadWrite, offline_access)
- [ ] Granted admin consent (if using organisational accounts)
- [ ] Set environment variables in `.env` (local) and DigitalOcean (production)
- [ ] Tested user login
- [ ] Tested email account connection
- [ ] Verified email syncing works

## Support

If you encounter issues not covered in this guide:
1. Check Azure AD application logs
2. Review application logs for specific error messages
3. Verify all environment variables are set correctly
4. Ensure redirect URIs match exactly
