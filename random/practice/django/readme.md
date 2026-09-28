AbstractBaseUser: Provides the core authentication machinery (like password hashing and session tokens) without any default fields.

BaseUserManager: The base class for handling database queries and record creation for the user model.

PermissionsMixin: Integrates Django's built-in group, permission, and superuser flags into your custom model.













The default UserCreationForm:
 is highly limited. It only asks for three things:UsernamePasswordPassword confirmationIf a website needs more details during signup—like an Email address, First Name, Phone Number, or Profile Picture—the default form will not work. Developers create a custom form like RegularUserSignupForm to add those missing fields.