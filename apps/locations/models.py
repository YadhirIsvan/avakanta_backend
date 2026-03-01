from django.db import models


class Country(models.Model):
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=10, unique=True, blank=True, null=True)

    class Meta:
        db_table = 'countries'
        verbose_name = 'Country'
        verbose_name_plural = 'Countries'
        ordering = ['name']

    def __str__(self):
        return self.name


class State(models.Model):
    name = models.CharField(max_length=150)
    country = models.ForeignKey(
        Country,
        on_delete=models.CASCADE,
        related_name='states'
    )
    code = models.CharField(max_length=20, blank=True, null=True)

    class Meta:
        db_table = 'states'
        verbose_name = 'State'
        verbose_name_plural = 'States'
        ordering = ['name']

    def __str__(self):
        return f'{self.name}, {self.country.name}'


class City(models.Model):
    name = models.CharField(max_length=150)
    state = models.ForeignKey(
        State,
        on_delete=models.CASCADE,
        related_name='cities'
    )

    class Meta:
        db_table = 'cities'
        verbose_name = 'City'
        verbose_name_plural = 'Cities'
        ordering = ['name']

    def __str__(self):
        return f'{self.name}, {self.state.name}'
