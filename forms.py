from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, FileField, TextAreaField, SelectField
from wtforms.validators import DataRequired, Length, EqualTo, ValidationError

class LoginForm(FlaskForm):
    username = StringField('用户名', validators=[DataRequired()])
    password = PasswordField('密码', validators=[DataRequired()])
    submit = SubmitField('登录')

class RegisterForm(FlaskForm):
    username = StringField('用户名', validators=[DataRequired(), Length(min=4, max=150)])
    password = PasswordField('密码', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('确认密码', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('注册')

class UploadForm(FlaskForm):
    files = FileField('选择文件', validators=[DataRequired()])
    share_type = SelectField('分享类型', choices=[
        ('public', '公开分享 - 所有人可见'),
        ('link_only', '链接分享 - 仅拥有链接的人可见'),
        ('specified_users', '指定用户 - 仅指定用户可见')
    ], default='public')
    allow_view = BooleanField('允许查看', default=True)
    allow_download = BooleanField('允许下载', default=True)
    allow_edit = BooleanField('允许编辑', default=False)
    password = PasswordField('访问密码（可选）')
    expiry_type = SelectField('过期设置', choices=[
        ('never', '永不过期'),
        ('hours', '指定小时数'),
        ('custom', '自定义时间')
    ], default='never')
    expiry_hours = SelectField('预设时间', choices=[
        ('1', '1小时'), ('24', '24小时'), ('168', '7天'), ('720', '30天')
    ])
    custom_expiry = StringField('自定义过期时间（YYYY-MM-DD HH:MM）')
    allowed_users = TextAreaField('允许的用户（用户名，每行一个）')
    submit = SubmitField('上传')

class ShareForm(FlaskForm):
    share_type = SelectField('分享类型', choices=[
        ('public', '公开分享 - 所有人可见'),
        ('link_only', '链接分享 - 仅拥有链接的人可见'),
        ('specified_users', '指定用户 - 仅指定用户可见')
    ])
    allow_view = BooleanField('允许查看')
    allow_download = BooleanField('允许下载')
    allow_edit = BooleanField('允许编辑')
    password = PasswordField('访问密码（可选）')
    expiry_type = SelectField('过期设置', choices=[
        ('never', '永不过期'),
        ('hours', '指定小时数'),
        ('custom', '自定义时间')
    ])
    expiry_hours = SelectField('预设时间', choices=[
        ('1', '1小时'), ('24', '24小时'), ('168', '7天'), ('720', '30天')
    ])
    custom_expiry = StringField('自定义过期时间（YYYY-MM-DD HH:MM）')
    allowed_users = TextAreaField('允许的用户（用户名，每行一个）')
    submit = SubmitField('更新分享设置')

class ConfigForm(FlaskForm):
    allow_registration = BooleanField('允许用户注册')
    default_max_file_size = StringField('默认单文件大小限制 (MB)', default='1024')
    default_max_total_files = StringField('默认总文件数量限制', default='100')
    default_max_total_size = StringField('默认总文件大小限制 (GB)', default='10')
    background_image = StringField('背景图片URL')
    default_theme = SelectField('默认主题', choices=[
        ('light', '亮色主题'),
        ('dark', '暗色主题'),
        ('auto', '跟随系统')
    ], default='light')
    default_language = SelectField('默认语言', choices=[
        ('zh', '中文'),
        ('en', 'English'),
        ('auto', '跟随系统')
    ], default='zh')
    primary_color = StringField('主题色', default='#667eea')
    submit = SubmitField('保存配置')

class ProfileForm(FlaskForm):
    nickname = StringField('昵称', validators=[Length(max=150)])
    avatar_url = StringField('头像链接', validators=[Length(max=500)])
    language = SelectField('语言', choices=[('zh', '中文'), ('en', 'English')])
    theme = SelectField('主题', choices=[('light', '亮色'), ('dark', '暗色')])
    submit = SubmitField('保存设置')

class UserLimitForm(FlaskForm):
    max_file_size = StringField('单文件大小限制 (MB)')
    max_total_files = StringField('总文件数量限制')
    max_total_size = StringField('总文件大小限制 (GB)')
    submit = SubmitField('更新限制')
