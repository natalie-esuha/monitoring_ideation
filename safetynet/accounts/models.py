from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager


class Role(models.Model):
    PERSON_AT_RISK = "Person at Risk"
    DESIGNATED_PERSON = "Designated Person"
    ADMIN = "Admin"

    role_id = models.AutoField(primary_key=True)
    role_name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.role_name


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra):
        if not email:
            raise ValueError("Email is required")
        user = self.model(email=self.normalize_email(email), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("role", Role.objects.get_or_create(role_name=Role.ADMIN)[0])
        return self.create_user(email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    GENDERS = [("Female", "Female"), ("Male", "Male"), ("Other", "Other")]

    user_id = models.AutoField(primary_key=True)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    email = models.EmailField(max_length=100, unique=True)
    phone_no = models.CharField(max_length=20)
    gender = models.CharField(max_length=10, choices=GENDERS)
    role = models.ForeignKey(Role, on_delete=models.PROTECT, null=True, related_name="users")
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = UserManager()
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name", "phone_no", "gender"]

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def role_name(self):
        return self.role.role_name if self.role else None


class PersonAtRisk(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True,
                                related_name="person_profile")

    def __str__(self):
        return str(self.user)


class DesignatedPerson(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True,
                                related_name="designated_profile")

    def __str__(self):
        return str(self.user)


class SupportLink(models.Model):
    person = models.ForeignKey(PersonAtRisk, on_delete=models.CASCADE, related_name="support_links")
    designated = models.ForeignKey(DesignatedPerson, on_delete=models.CASCADE, related_name="supported")
    relationship_type = models.CharField(max_length=50)
    date_linked = models.DateField(auto_now_add=True)

    class Meta:
        unique_together = ("person", "designated")
